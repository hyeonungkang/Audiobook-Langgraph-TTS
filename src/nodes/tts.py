"""
TTS Generator node for LangGraph TTS Audiobook Converter
"""
from pathlib import Path
from datetime import datetime
from ..state import AgentState
# utils.py와 utils/__init__.py를 구분하여 import
from ..utils import (
    log_error,
    log_workflow_step_start,
    log_workflow_step_end
)
# utils.py의 함수들은 직접 import
import importlib.util
import sys
from pathlib import Path

utils_py_path = Path(__file__).parent.parent / "utils.py"
if utils_py_path.exists():
    spec = importlib.util.spec_from_file_location("src.utils_module", utils_py_path)
    utils_module = importlib.util.module_from_spec(spec)
    sys.modules["src.utils_module"] = utils_module
    spec.loader.exec_module(utils_module)
    
    text_to_speech_from_chunks = utils_module.text_to_speech_from_chunks
    text_to_speech_radio_show = utils_module.text_to_speech_radio_show
    text_to_speech_radio_show_structured = utils_module.text_to_speech_radio_show_structured
    chunk_text_for_tts = utils_module.chunk_text_for_tts
    parse_radio_show_dialogue = utils_module.parse_radio_show_dialogue
    merge_dialogue_chunks = utils_module.merge_dialogue_chunks
    remove_ssml_tags = utils_module.remove_ssml_tags
    get_mode_profile = utils_module.get_mode_profile
    sanitize_path_component = utils_module.sanitize_path_component
else:
    raise ImportError(f"Cannot find utils.py at {utils_py_path}")


def tts_generator_node(state: AgentState) -> AgentState:
    """
    TTS Generator 노드: Writer가 생성한 스크립트를 TTS로 변환
    
    Args:
        state: AgentState
        
    Returns:
        업데이트된 AgentState
    """
    try:
        # 워크플로우 타이밍 시작
        start_time = log_workflow_step_start("tts_generator")
        print("\n[TTS Generator] Starting...", flush=True)
        
        scripts = state.get("scripts", [])
        config = state["config"]
        language = config.get("language", "ko")
        narrative_mode = config.get("narrative_mode", "mentor")
        voice_profile = config.get("voice_profile")
        radio_single_request = config.get("radio_show_single_request", True)
        tts_backend = config.get("tts_backend", "cloud")
        tts_model_name = config.get("tts_model_name", "gemini-2.5-pro-tts")
        tts_genai_model_id = config.get("tts_genai_model_id", "gemini-2.5-flash-preview-tts")
        
        if not scripts:
            print("  ⚠ Warning: No scripts to process", flush=True)
            print(f"  Debug: State keys = {list(state.keys())}", flush=True)
            print(f"  Debug: Segments count = {len(state.get('segments', []))}", flush=True)
            print(f"  Debug: Scripts type = {type(scripts)}, length = {len(scripts) if scripts else 0}", flush=True)
            
            # writer_map_node가 실행되었는지 확인
            errors = state.get("errors", [])
            writer_errors = [e for e in errors if e.get("node_name") == "writer_map" or e.get("node_name") == "writer_worker"]
            if writer_errors:
                print(f"  Debug: Writer errors found: {len(writer_errors)}", flush=True)
                for err in writer_errors[:3]:  # 최대 3개만 출력
                    print(f"    - {err.get('error_message', 'Unknown error')}", flush=True)
            
            log_workflow_step_end("tts_generator", start_time)
            return state
        
        # 스크립트를 세그먼트 ID 순서대로 정렬
        scripts_sorted = sorted(scripts, key=lambda x: x.get("segment_id", 0))
        
        # 전체 스크립트 텍스트 결합
        full_text = ""
        valid_scripts_count = 0
        for script_data in scripts_sorted:
            script_text = script_data.get("script", "").strip()
            if script_text:
                # SSML 제거는 단일 화자용. 라디오쇼에서는 원본 라벨/마크업을 보존.
                if narrative_mode != "radio_show":
                    script_text = remove_ssml_tags(script_text)
                
                full_text += script_text + "\n\n"
                valid_scripts_count += 1
        
        # full_text 검증
        if not full_text.strip():
            print("  ⚠ Warning: full_text is empty after combining scripts", flush=True)
            print(f"  Debug: Total scripts = {len(scripts_sorted)}, Valid scripts = {valid_scripts_count}", flush=True)
            print(f"  Debug: Sample script data = {scripts_sorted[0] if scripts_sorted else 'None'}", flush=True)
            error_info = {
                "node_name": "tts_generator",
                "error_message": "full_text is empty - no valid script content found",
                "segment_id": None
            }
            state["errors"].append(error_info)
            return state
        
        print(f"  ✓ Combined {valid_scripts_count} valid scripts, total text length: {len(full_text)} chars", flush=True)
        
        if narrative_mode == "radio_show":
            # 라디오쇼: 두 화자의 대화를 분리 후 화자별 음성으로 합성
            print(f"\nTTS: Radio show mode detected. Parsing dialogues...", flush=True)
            dialogues = parse_radio_show_dialogue(full_text)
            dialogues = merge_dialogue_chunks(dialogues)
            
            if not dialogues:
                # 1차 파싱 실패 시, 단순 라인 단위 교대 생성 시도 (Fallback)
                print("  ⚠ Warning: No dialogue found. Applying fallback alternating Host 1/2...", flush=True)
                lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]
                alt_dialogues = []
                current_speaker = 1
                for ln in lines:
                    alt_dialogues.append({"speaker": current_speaker, "text": ln})
                    current_speaker = 2 if current_speaker == 1 else 1
                dialogues = alt_dialogues
            
            # 최종적으로도 비어 있으면 중단
            if not dialogues:
                print("  ✗ Error: Radio show dialog parsing failed (empty).", flush=True)
                error_info = {
                    "node_name": "tts_generator",
                    "error_message": "Radio show mode: No dialogue extracted",
                    "segment_id": None
                }
                state["errors"].append(error_info)
                return state
            
            host1 = voice_profile.get("host1") if isinstance(voice_profile, dict) else None
            host2 = voice_profile.get("host2") if isinstance(voice_profile, dict) else None
            if not host1 or not host2:
                print("  ⚠ Warning: host1/host2 voice profiles are missing", flush=True)
                error_info = {
                    "node_name": "tts_generator",
                    "error_message": "Radio show mode: host1/host2 profiles required",
                    "segment_id": None
                }
                state["errors"].append(error_info)
                return state
            
            audio_title = state.get("audio_title", "output")
            # 파일명에 두 화자 이름 포함
            voice_name = f"{host1.get('name', 'Host1')}-{host2.get('name', 'Host2')}"
            mode_key = narrative_mode
            lang_short = "KO" if language == "ko" else "EN"
            title_safe = sanitize_path_component(audio_title)
            voice_safe = sanitize_path_component(voice_name)
            temp_output_path = Path(__file__).parent.parent.parent / "temp_output" / f"{title_safe}_{mode_key}_{voice_safe}_{lang_short}.mp3"
            temp_output_path.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"\nTTS: Converting {len(dialogues)} dialogues (radio show)...", flush=True)
            print(f"  Output path: {temp_output_path}", flush=True)
            print(f"  Voice profile: host1={host1}, host2={host2}", flush=True)
            
            if radio_single_request:
                # 구조적 배치 청킹 후 멀티스피커 합성 (안정성 우선)
                rep_voice = host1.get("name") if isinstance(host1, dict) else None
                host1_name = host1.get("name") if isinstance(host1, dict) else None
                host2_name = host2.get("name") if isinstance(host2, dict) else None
                text_to_speech_radio_show_structured(
                    dialogues=dialogues,
                    output_filename=str(temp_output_path),
                    language=language,
                    model_name=tts_model_name,
                    representative_voice=rep_voice,
                    host1_voice=host1_name,
                    host2_voice=host2_name,
                    narrative_mode=narrative_mode,
                    tts_backend=tts_backend,
                    genai_tts_model_id=tts_genai_model_id,
                )
            else:
                # 화자별 개별 합성 후 병합 (기존 안전 경로)
                text_to_speech_radio_show(
                    dialogues=dialogues,
                    output_filename=str(temp_output_path),
                    voice_profile=voice_profile,
                    language=language,
                    narrative_mode=narrative_mode,
                    tts_backend=tts_backend,
                    tts_model_name=tts_model_name,
                    genai_tts_model_id=tts_genai_model_id,
                )
            
            if not temp_output_path.exists():
                print(f"  ⚠ Warning: Audio file was not created: {temp_output_path}", flush=True)
                error_info = {
                    "node_name": "tts_generator",
                    "error_message": f"Audio file not created: {temp_output_path}",
                    "segment_id": None
                }
                state["errors"].append(error_info)
                return state
            
            file_size = temp_output_path.stat().st_size
            print(f"  ✓ Radio show audio created: {temp_output_path} ({file_size} bytes)", flush=True)
            state["audio_paths"] = [str(temp_output_path)]
            state["final_audio_path"] = str(temp_output_path)
            duration = log_workflow_step_end("tts_generator", start_time)
            print(f"TTS completed: {temp_output_path.name} (Duration: {duration:.1f}s)", flush=True)
        
        else:
            # 단일 화자 모드 (기존 로직)
            print(f"\nTTS: Chunking {len(scripts_sorted)} scripts for TTS...", flush=True)
            audio_chunks = chunk_text_for_tts(full_text, language=language)
            
            if not audio_chunks:
                print("  ⚠ Warning: No audio chunks generated from text", flush=True)
                print(f"  Debug: full_text length = {len(full_text)}", flush=True)
                error_info = {
                    "node_name": "tts_generator",
                    "error_message": "No audio chunks generated",
                    "segment_id": None
                }
                state["errors"].append(error_info)
                return state
            
            state["audio_chunks"] = audio_chunks
            print(f"  ✓ Generated {len(audio_chunks)} audio chunks", flush=True)
            
            # 즉시 임시 파일로 저장 (청킹 결과)
            try:
                temp_dir = Path(__file__).parent.parent.parent / "temp_output"
                temp_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_file = temp_dir / f"tts_chunks_{timestamp}.txt"
                
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(f"Total chunks: {len(audio_chunks)}\n")
                    f.write("=" * 70 + "\n\n")
                    for i, chunk in enumerate(audio_chunks):
                        f.write(f"[Chunk {i+1}/{len(audio_chunks)}]\n")
                        f.write(f"Length: {len(chunk)} chars\n")
                        f.write("-" * 70 + "\n")
                        f.write(chunk)
                        f.write("\n\n" + "=" * 70 + "\n\n")
                print(f"  ✓ TTS chunks saved to temp file: {temp_file}", flush=True)
            except Exception as e:
                log_error(f"Failed to save TTS chunks to temp file: {e}", context="tts_generator_node", exception=e)
                print(f"  ⚠ Warning: Failed to save TTS chunks to temp file: {e}", flush=True)
            
            # TTS 변환을 위한 임시 파일 경로 생성
            audio_title = state.get("audio_title", "output")
            voice_name = voice_profile.get("name", "Achernar") if voice_profile else "Achernar"
            language_code = "ko-KR" if language == "ko" else "en-US"
            
            # 모드 키와 언어 코드를 간단하게 변환
            mode_key = narrative_mode  # 영어 키 사용 (mentor, friend, lover, radio_show)
            lang_short = "KO" if language == "ko" else "EN"
            
            # 파일명 형식: {title}_{mode}_{voice}_{lang}.mp3
            title_safe = sanitize_path_component(audio_title)
            voice_safe = sanitize_path_component(voice_name)
            
            output_filename = f"{title_safe}_{mode_key}_{voice_safe}_{lang_short}.mp3"
            temp_output_path = Path(__file__).parent.parent.parent / "temp_output" / output_filename
            temp_output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # TTS 변환 실행
            print(f"\nTTS: Converting {len(audio_chunks)} chunks to speech...", flush=True)
            print(f"  Output path: {temp_output_path}", flush=True)
            print(f"  Voice profile: {voice_profile}", flush=True)
            print(f"  Language: {language}", flush=True)
            
            try:
                text_to_speech_from_chunks(
                    text_chunks=audio_chunks,
                    output_filename=str(temp_output_path),
                    voice_profile=voice_profile,
                    language=language,
                    narrative_mode=narrative_mode,
                    tts_backend=tts_backend,
                    tts_model_name=tts_model_name,
                    genai_tts_model_id=tts_genai_model_id,
                )
                
                # 생성된 오디오 파일 확인
                if not temp_output_path.exists():
                    print(f"  ⚠ Warning: Audio file was not created: {temp_output_path}", flush=True)
                    error_info = {
                        "node_name": "tts_generator",
                        "error_message": f"Audio file not created: {temp_output_path}",
                        "segment_id": None
                    }
                    state["errors"].append(error_info)
                    return state
                
                file_size = temp_output_path.stat().st_size
                print(f"  ✓ Audio file created: {temp_output_path} ({file_size} bytes)", flush=True)
                
                # 생성된 오디오 파일 경로 저장
                state["audio_paths"] = [str(temp_output_path)]
                state["final_audio_path"] = str(temp_output_path)
                
                # 워크플로우 타이밍 완료
                duration = log_workflow_step_end("tts_generator", start_time)
                print(f"TTS completed: {output_filename} (Duration: {duration:.1f}s)", flush=True)
            except Exception as e:
                error_info = {
                    "node_name": "tts_generator",
                    "error_message": f"TTS conversion failed: {str(e)}",
                    "segment_id": None
                }
                state["errors"].append(error_info)
                log_error(f"TTS conversion failed: {e}", context="tts_generator_node", exception=e)
                print(f"  ✗ TTS conversion failed: {e}", flush=True)
                import traceback
                traceback.print_exc()
                return state
        
        return state
        
    except Exception as e:
        error_info = {
            "node_name": "tts_generator",
            "error_message": str(e),
            "segment_id": None
        }
        state["errors"].append(error_info)
        log_error(f"TTS generator node error: {e}", context="tts_generator_node", exception=e)
        print(f"TTS generator node error: {e}", flush=True)
        return state

