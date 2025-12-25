"""
Showrunner node for LangGraph TTS Audiobook Converter
"""
import json
from pathlib import Path
from datetime import datetime
from ..state import AgentState
from ..utils import (
    enforce_segment_count,
    get_gemini_model,
    generate_content_with_retry,
    extract_key_sections,
    build_showrunner_prompt,
    log_error,
    validate_segments_quality,
    log_workflow_step_start,
    log_workflow_step_end
)


def showrunner_node(state: AgentState) -> AgentState:
    """
    Showrunner 노드: 논문을 15개 세그먼트로 분해하고 제목 생성
    
    Args:
        state: AgentState
        
    Returns:
        업데이트된 AgentState
    """
    try:
        # 워크플로우 타이밍 시작
        start_time = log_workflow_step_start("showrunner")
        print("\n[Showrunner] Starting...", flush=True)
        
        original_text = state["original_text"]
        config = state["config"]
        language = config.get("language", "ko")
        listener_name = config.get("listener_name", "현웅")
        narrative_mode = config.get("narrative_mode", "mentor")
        content_category = config.get("content_category", "research_paper")
        
        # ✅ 요구사항: abstract_outline 제거. 논문 모드도 showrunner가 원문만 보고 직접 세그먼트 생성.
        # ✅ showrunner는 반드시 Pro 사용
        gemini_model_pro = "gemini-2.5-pro"
        
        max_retries = 3
        previous_errors: list[str] = []
        segments: list[dict] = []
        audio_title = "Research_Paper_Audio"
        last_error_messages: list[str] = []

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[Showrunner] Attempt {attempt}/{max_retries}", flush=True)
                candidate_segments, candidate_title = showrunner_step(
                    original_text,
                    language=language,
                    listener_name=listener_name,
                    narrative_mode=narrative_mode,
                    content_category=content_category,
                    gemini_model=gemini_model_pro,
                    previous_errors=previous_errors,
                )

                # 세그먼트 개수 강제 (15개)
                candidate_segments = enforce_segment_count(candidate_segments, target=15)

                is_valid, error_messages = validate_segments_quality(candidate_segments, language=language)
                if is_valid:
                    segments = candidate_segments
                    audio_title = candidate_title
                    print(f"  ✓ Attempt {attempt}: segments passed validation", flush=True)
                    break

                last_error_messages = error_messages
                previous_errors.extend(error_messages)
                summary = "; ".join(error_messages[:3])
                print(f"  ⚠ Attempt {attempt}: validation failed -> {summary}", flush=True)

            except Exception as e:
                err_msg = f"Attempt {attempt} error: {e}"
                last_error_messages = [err_msg]
                previous_errors.append(err_msg)
                log_error(err_msg, context="showrunner_node", exception=e)
                print(f"  ⚠ {err_msg}", flush=True)
        else:
            # 모든 시도 실패
            error_info = {
                "node_name": "showrunner",
                "error_message": "; ".join(last_error_messages) if last_error_messages else "Showrunner failed after retries",
                "segment_id": None
            }
            state["errors"].append(error_info)
            log_error(error_info["error_message"], context="showrunner_node")
            print("Showrunner failed after retries. See errors for details.", flush=True)
            return state
        
        # State 업데이트
        state["segments"] = segments
        state["audio_title"] = audio_title
        
        # 즉시 임시 파일로 저장 (중간 결과 저장)
        try:
            temp_dir = Path(__file__).parent.parent.parent / "temp_output"
            temp_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_file = temp_dir / f"showrunner_segments_{timestamp}.json"
            
            output_data = {
                "audio_title": audio_title,
                "segments": segments
            }
            
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"  ✓ Segments saved to temp file: {temp_file}", flush=True)

        except Exception as e:
            log_error(f"Failed to save segments to temp file: {e}", context="showrunner_node", exception=e)
            print(f"  ⚠ Warning: Failed to save segments to temp file: {e}", flush=True)
        
        # 워크플로우 타이밍 완료
        duration = log_workflow_step_end("showrunner", start_time)
        print(f"Showrunner completed: {len(segments)} segments, title: {audio_title} (Duration: {duration:.1f}s)", flush=True)
        
        return state
        
    except Exception as e:
        error_info = {
            "node_name": "showrunner",
            "error_message": str(e),
            "segment_id": None
        }
        state["errors"].append(error_info)
        log_error(f"Showrunner node error: {e}", context="showrunner_node", exception=e)
        print(f"Showrunner node error: {e}", flush=True)
        # 에러가 발생해도 다음 노드로 진행 (segments가 비어있으면 조건부 엣지에서 처리)
        return state


def showrunner_step(
    original_text: str,
    language: str,
    listener_name: str,
    narrative_mode: str,
    content_category: str = "research_paper",
    gemini_model: str = None,
    previous_errors: list[str] | None = None,
) -> tuple[list[dict], str]:
    """
    Showrunner 단계: 텍스트를 15개 세그먼트로 분해하고 제목 생성
    
    Args:
        original_text: 원본 텍스트
        language: 언어 ("ko" 또는 "en")
        listener_name: 청취자 이름
        narrative_mode: 서사 모드
        content_category: 콘텐츠 카테고리
        gemini_model: Gemini 모델 키 ("gemini-2.5-pro" 또는 "gemini-2.5-flash")
        previous_errors: 이전 시도에서 발견된 문제 목록
        
    Returns:
        (segments, audio_title) 튜플
    """
    previous_errors = previous_errors or []
    model = get_gemini_model(gemini_model)
    
    # 핵심 섹션만 추출 (토큰 절약)
    from ..config import MAX_SHOWRUNNER_INPUT_LENGTH
    paper_content = extract_key_sections(original_text, max_length=MAX_SHOWRUNNER_INPUT_LENGTH)
    
    # 프롬프트 생성
    config = {
        "category": content_category,
        "narrative_mode": narrative_mode,
        "language": language
    }
    prompt = build_showrunner_prompt(
        text=paper_content,
        config=config,
        previous_errors=previous_errors
    )
    
    # 디버그 로그 (개발용, 환경 변수로 제어)
    from ..config import DEBUG_LOG_ENABLED, DEBUG_LOG_PATH
    if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
        try:
            DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                from time import time
                log_entry = {
                    "sessionId": "debug-session",
                    "runId": "showrunner-debug-1",
                    "hypothesisId": "H1,H3",
                    "location": "showrunner.py:showrunner_step",
                    "message": "Showrunner prompt/inputs before generate_content_with_retry",
                    "data": {
                        "language": language,
                        "content_category": content_category,
                        "paper_content_bytes": len((paper_content or '').encode('utf-8')),
                        "prompt_len_chars": len(prompt),
                        "prompt_len_bytes": len(prompt.encode('utf-8'))
                    },
                    "timestamp": int(time() * 1000)
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except:
            pass
    
    print("\n[Showrunner] Generating segments...", flush=True)
    
    # Gemini API 호출
    try:
        # ✅ showrunner는 충분히 길어질 수 있으므로 타임아웃 없이 기다리되, 모델 폴백(Flash 전환)은 금지
        response = generate_content_with_retry(
            model,
            prompt,
            enable_model_fallback=False,
            timeout_seconds=None,
        )
        response_text = response.text.strip()

        from ..utils import _extract_json_text
        result = json.loads(_extract_json_text(response_text))
        segments = result.get("segments", [])
        audio_title = result.get("audio_title", "Research_Paper_Audio")
        
        # 세그먼트 검증
        if not segments or len(segments) == 0:
            print("  ⚠ Warning: No segments in response, generating default segments", flush=True)
            raise ValueError("No segments generated")
        
        # 세그먼트 ID 확인 및 수정
        for i, seg in enumerate(segments):
            if "segment_id" not in seg:
                seg["segment_id"] = i + 1
            
            # 필수 필드 검증
            required_fields = ["title", "core_content", "instruction_for_writer", "opening_line", "closing_line"]
            for field in required_fields:
                if field not in seg:
                    seg[field] = ""
            
            # math_focus는 선택 필드
            if "math_focus" not in seg:
                seg["math_focus"] = ""
        
        print(f"  ✓ Generated {len(segments)} segments", flush=True)
        return segments, audio_title
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        log_error(f"Failed to parse showrunner response: {e}", context="showrunner_step", exception=e)
        
        # 응답 텍스트 저장 (디버깅용)
        try:
            debug_file = Path(__file__).parent.parent.parent / "temp_output" / f"showrunner_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            debug_file.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write("=== ERROR ===\n")
                f.write(f"{str(e)}\n\n")
                f.write("=== RESPONSE TEXT ===\n")
                f.write(response_text[:2000] if 'response_text' in locals() else "No response text available")
            print(f"  ⚠ Error details saved to: {debug_file}", flush=True)
        except Exception as save_error:
            print(f"  ⚠ Failed to save error details: {save_error}", flush=True)
        
        # 개선된 fallback: 입력 텍스트 기반 기본 세그먼트 생성
        print("  ⚠ Using fallback: Generating basic segment structure", flush=True)
        segments = []
        for i in range(15):
            segments.append({
                "segment_id": i + 1,
                "title": f"세그먼트 {i + 1}" if language == "ko" else f"Segment {i + 1}",
                "core_content": "내용을 채워주세요" if language == "ko" else "Please fill in content",
                "instruction_for_writer": "자연스러운 오디오 스크립트를 작성하세요" if language == "ko" else "Write a natural audio script",
                "math_focus": "",
                "opening_line": "",
                "closing_line": ""
            })
        return segments, "Research_Paper_Audio"
    
    except Exception as e:
        log_error(f"Unexpected error in showrunner_step: {e}", context="showrunner_step", exception=e)
        print(f"  ⚠ Unexpected error: {e}", flush=True)
        # 최종 fallback
        segments = []
        for i in range(15):
            segments.append({
                "segment_id": i + 1,
                "title": f"세그먼트 {i + 1}" if language == "ko" else f"Segment {i + 1}",
                "core_content": "",
                "instruction_for_writer": "",
                "math_focus": "",
                "opening_line": "",
                "closing_line": ""
            })
        return segments, "Research_Paper_Audio"

