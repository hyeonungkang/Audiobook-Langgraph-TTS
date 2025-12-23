"""
TTS Generator node for LangGraph TTS Audiobook Converter
"""
from pathlib import Path
from datetime import datetime
from ..state import AgentState
from ..utils import (
    text_to_speech_from_chunks,
    chunk_text_for_tts,
    parse_radio_show_dialogue,
    merge_dialogue_chunks,
    remove_ssml_tags,
    get_tts_prompt_for_mode,
    get_mode_profile,
    sanitize_path_component,
    log_error,
    log_workflow_step_start,
    log_workflow_step_end
)


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
                # SSML 태그 제거
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
        
        # TTS 프롬프트 가져오기
        mode_profile = get_mode_profile(narrative_mode)
        tts_prompt = get_tts_prompt_for_mode(mode_profile, language)
        
        # 텍스트 청킹
        print(f"\nTTS: Chunking {len(scripts_sorted)} scripts for TTS...", flush=True)
        audio_chunks = chunk_text_for_tts(full_text, language=language, tts_prompt=tts_prompt)
        
        if not audio_chunks:
            print("  ⚠ Warning: No audio chunks generated from text", flush=True)
            print(f"  Debug: full_text length = {len(full_text)}, tts_prompt length = {len(tts_prompt)}", flush=True)
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
                tts_prompt=tts_prompt
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

