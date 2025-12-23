"""
Writer node for LangGraph TTS Audiobook Converter
"""
from typing import Annotated
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..state import AgentState
from ..utils import (
    get_gemini_model,
    generate_content_with_retry,
    extract_relevant_sections,
    build_writer_prompt,
    log_error,
    log_workflow_step_start,
    log_workflow_step_end
)


def writer_map_node(state: AgentState) -> AgentState:
    """
    Writer Map 노드: 모든 세그먼트를 병렬로 처리하여 스크립트 생성
    (langgraph 1.0.4에서는 Send API가 없으므로 ThreadPoolExecutor 사용)
    
    Args:
        state: AgentState
        
    Returns:
        업데이트된 AgentState (scripts 필드에 결과 저장)
    """
    # 워크플로우 타이밍 시작
    start_time = log_workflow_step_start("writer_map")
    print("\n[Writer Map] Starting...", flush=True)
    
    segments = state.get("segments", [])
    config = state["config"]
    
    if not segments:
        print("Writer Map: No segments to process", flush=True)
        log_workflow_step_end("writer_map", start_time)
        state["scripts"] = []
        return state
    
    original_text = state.get("original_text", "")
    language = config.get("language", "ko")
    listener_name = config.get("listener_name", "용사")
    narrative_mode = config.get("narrative_mode", "mentor")
    voice_profile = config.get("voice_profile")
    content_category = config.get("content_category", "research_paper")
    # ✅ 요구사항: Flash(또는 사용자 선택 모델)는 writer에만 적용
    # - frontend/CLI에서 넘어오는 gemini_model(=model 선택)을 writer 모델로 취급
    # - 필요 시 gemini_model_writer로 별도 지정 가능
    gemini_model = config.get("gemini_model_writer") or config.get("gemini_model") or "gemini-2.5-flash"
    
    print(f"Writer Map: Processing {len(segments)} segments in parallel...", flush=True)
    
    # 병렬 처리로 모든 세그먼트 처리
    scripts = []
    errors = []
    
    def process_segment(segment):
        """단일 세그먼트 처리"""
        segment_id = segment.get("segment_id", 0)
        try:
            print(f"  Writer {segment_id}: Processing segment {segment_id}...", flush=True)
            
            script = writer_step(
                segment_info=segment,
                original_text=original_text,
                language=language,
                listener_name=listener_name,
                narrative_mode=narrative_mode,
                voice_profile=voice_profile,
                content_category=content_category,
                gemini_model=gemini_model
            )
            
            print(f"  Writer {segment_id}: Completed", flush=True)
            return {
                "segment_id": segment_id,
                "script": script
            }
        except Exception as e:
            error_info = {
                "node_name": "writer_worker",
                "error_message": str(e),
                "segment_id": segment_id
            }
            log_error(f"Writer worker error (segment {segment_id}): {e}", context="writer_map_node", exception=e)
            print(f"  Writer {segment_id}: Error - {e}", flush=True)
            return {
                "segment_id": segment_id,
                "script": f"[ERROR: Failed to generate script for segment {segment_id}]",
                "error": error_info
            }
    
    # ThreadPoolExecutor를 사용한 병렬 처리
    with ThreadPoolExecutor(max_workers=min(len(segments), 5)) as executor:
        future_to_segment = {executor.submit(process_segment, segment): segment for segment in segments}
        
        results = []
        for future in as_completed(future_to_segment):
            result = future.result()
            results.append(result)
    
    # 세그먼트 ID 순서대로 정렬
    results_sorted = sorted(results, key=lambda x: x.get("segment_id", 0))
    
    # scripts와 errors 분리
    for result in results_sorted:
        if "error" in result:
            errors.append(result["error"])
        scripts.append({
            "segment_id": result.get("segment_id"),
            "script": result.get("script", "")
        })
    
    # State 업데이트
    state["scripts"] = scripts
    state["errors"].extend(errors)
    
    # 즉시 임시 파일로 저장 (데이터 저장 안정화)
    if scripts:
        try:
            temp_dir = Path(__file__).parent.parent.parent / "temp_output"
            temp_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_file = temp_dir / f"writer_scripts_{timestamp}.txt"
            
            # 세그먼트 ID 순서대로 정렬
            scripts_sorted_for_save = sorted(scripts, key=lambda x: x.get("segment_id", 0))
            full_script = "\n\n".join([f"[Segment {s.get('segment_id', 0)}]\n{s.get('script', '')}" for s in scripts_sorted_for_save])
            
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(full_script)
            print(f"  ✓ Scripts saved to temp file: {temp_file}", flush=True)
        except Exception as e:
            log_error(f"Failed to save scripts to temp file: {e}", context="writer_map_node", exception=e)
            print(f"  ⚠ Warning: Failed to save scripts to temp file: {e}", flush=True)
    
    # State 저장 검증
    if len(state["scripts"]) != len(segments):
        print(f"  ⚠ Warning: Scripts count ({len(state['scripts'])}) != Segments count ({len(segments)})", flush=True)
        missing_segments = set(range(1, len(segments) + 1)) - {s.get("segment_id", 0) for s in state["scripts"]}
        if missing_segments:
            print(f"  ⚠ Missing segment IDs: {sorted(missing_segments)}", flush=True)
    else:
        print(f"  ✓ Scripts count matches segments count: {len(state['scripts'])}", flush=True)
    
    # 결과 출력 및 에러 복구 메커니즘
    failed_segments = [r.get("segment_id") for r in results_sorted if "error" in r]
    successful_segments = [s.get("segment_id") for s in scripts if s.get("script", "").strip() and not s.get("script", "").strip().startswith("[ERROR:")]
    
    if failed_segments:
        print(f"  ⚠ Warning: {len(failed_segments)} segments failed: {failed_segments}", flush=True)
        print(f"  ✓ {len(successful_segments)} segments succeeded: {successful_segments}", flush=True)
        
        # 최소한의 scripts가 있으면 계속 진행 (부분 실패 허용)
        if len(successful_segments) > 0:
            print(f"  → Proceeding with {len(successful_segments)} successful scripts", flush=True)
        else:
            # 모든 세그먼트가 실패한 경우
            error_info = {
                "node_name": "writer_map",
                "error_message": f"All {len(segments)} segments failed to generate scripts",
                "segment_id": None
            }
            state["errors"].append(error_info)
            print(f"  ✗ Error: All segments failed. Cannot proceed to TTS.", flush=True)
    else:
        print(f"  ✓ All {len(scripts)} scripts generated successfully", flush=True)
    
    # 워크플로우 타이밍 완료
    duration = log_workflow_step_end("writer_map", start_time)
    print(f"Writer Map completed (Duration: {duration:.1f}s)", flush=True)
    
    return state


def writer_step(
    segment_info: dict,
    original_text: str,
    language: str,
    listener_name: str,
    narrative_mode: str = "mentor",
    voice_profile: dict = None,
    content_category: str = "research_paper",
    gemini_model: str = None
) -> str:
    """
    Writer 단계: 세그먼트를 스크립트로 변환
    
    Args:
        segment_info: 세그먼트 정보 (segment_id, opening_line, closing_line 등)
        original_text: 원본 텍스트
        language: 언어 ("ko" 또는 "en")
        listener_name: 청취자 이름
        narrative_mode: 서사 모드
        voice_profile: 음성 프로필 (선택적)
        content_category: 콘텐츠 카테고리
        gemini_model: Gemini 모델 키 ("gemini-2.5-pro" 또는 "gemini-2.5-flash")
        
    Returns:
        생성된 스크립트 텍스트
    """
    model = get_gemini_model(gemini_model)
    
    # 관련 섹션만 추출 (토큰 절약)
    from ..config import MAX_WRITER_INPUT_LENGTH
    paper_content = extract_relevant_sections(original_text, segment_info, max_length=MAX_WRITER_INPUT_LENGTH)
    
    # 프롬프트 생성
    config = {
        "narrative_mode": narrative_mode,
        "language": language,
        "listener_name": listener_name,
        "category": content_category
    }
    prompt = build_writer_prompt(
        segment_info=segment_info,
        full_text=paper_content,
        config=config
    )
    
    segment_id = segment_info.get("segment_id", 0)
    print(f"  Writer {segment_id}: Generating script...", flush=True)
    
    # Gemini API 호출
    response = generate_content_with_retry(model, prompt)
    script = response.text.strip()
    
    # SSML 태그나 마크다운 제거
    if script.startswith("```"):
        lines = script.split("\n")
        script = "\n".join(lines[1:-1]) if len(lines) > 2 else script
    
    print(f"  Writer {segment_id}: Script generated ({len(script)} chars)", flush=True)
    return script


def writer_worker_node(segment: dict) -> dict:
    """
    Writer Worker 노드: 단일 세그먼트를 처리하여 스크립트 생성
    
    Args:
        segment: 세그먼트 정보 딕셔너리
        
    Returns:
        {"segment_id": int, "script": str} 딕셔너리
    """
    # State에서 필요한 정보를 가져오기 위해 전역 상태 접근 필요
    # LangGraph의 Send 패턴에서는 별도로 전달해야 하므로, 
    # 실제로는 State를 전달받아야 함
    # 여기서는 간단한 구현을 위해 segment만 받도록 함
    
    # 실제 구현에서는 State 전체를 전달받거나, 
    # Context를 통해 접근해야 함
    # 임시로 segment에 필요한 정보를 포함시키도록 함
    
    segment_id = segment.get("segment_id", 0)
    
    try:
        # segment 딕셔너리에 필요한 정보가 모두 포함되어 있다고 가정
        # 실제로는 State에서 가져와야 함
        original_text = segment.get("_original_text", "")
        language = segment.get("_language", "ko")
        listener_name = segment.get("_listener_name", "용사")
        narrative_mode = segment.get("_narrative_mode", "mentor")
        voice_profile = segment.get("_voice_profile")
        
        print(f"  Writer {segment_id}: Processing segment {segment_id}...", flush=True)
        
        # Writer 실행
        script = writer_step(
            segment_info=segment,
            original_text=original_text,
            language=language,
            listener_name=listener_name,
            narrative_mode=narrative_mode,
            voice_profile=voice_profile
        )
        
        print(f"  Writer {segment_id}: Completed", flush=True)
        
        return {
            "segment_id": segment_id,
            "script": script
        }
        
    except Exception as e:
        error_info = {
            "node_name": "writer_worker",
            "error_message": str(e),
            "segment_id": segment_id
        }
        log_error(f"Writer worker error (segment {segment_id}): {e}", context="writer_worker_node", exception=e)
        print(f"  Writer {segment_id}: Error - {e}", flush=True)
        
        # 에러가 발생해도 빈 스크립트 반환 (다른 세그먼트는 계속 처리)
        return {
            "segment_id": segment_id,
            "script": f"[ERROR: Failed to generate script for segment {segment_id}]",
            "error": error_info
        }


# writer_reduce_node는 더 이상 필요 없음 (writer_map_node에서 직접 처리)
# 하지만 그래프 호환성을 위해 유지 (빈 함수로)
def writer_reduce_node(state: AgentState) -> AgentState:
    """
    Writer Reduce 노드: 더 이상 필요 없음 (writer_map_node에서 직접 처리)
    그래프 호환성을 위해 유지
    
    Args:
        state: AgentState
        
    Returns:
        AgentState (변경 없음)
    """
    return state

