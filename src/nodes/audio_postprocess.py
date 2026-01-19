"""
Audio PostProcess node for LangGraph TTS Audiobook Converter
"""
import shutil
import time
from pathlib import Path
from ..config import OUTPUT_ROOT, ADDITIONAL_OUTPUT_ROOT
from ..state import AgentState
from ..utils import (
    prepare_output_directory,
    build_output_paths,
    save_latest_run_path,
    log_error,
    log_workflow_step_start,
    log_workflow_step_end,
    ensure_cover_art_jpeg,
    add_mp3_metadata,
)


def audio_postprocess_node(state: AgentState) -> AgentState:
    """
    Audio PostProcess 노드: 오디오 파일을 최종 위치로 이동하고 출력 파일 정리
    
    Args:
        state: AgentState
        
    Returns:
        업데이트된 AgentState
    """
    try:
        # 워크플로우 타이밍 시작
        start_time = log_workflow_step_start("audio_postprocess")
        print("\n[Audio PostProcess] Starting...", flush=True)
        
        final_audio_path = state.get("final_audio_path")
        if not final_audio_path:
            print("  ⚠ Warning: No audio file to process", flush=True)
            log_workflow_step_end("audio_postprocess", start_time)
            return state
        
        config = state["config"]
        audio_title = state.get("audio_title", "output")
        voice_profile = config.get("voice_profile")
        language = config.get("language", "ko")
        narrative_mode = config.get("narrative_mode", "mentor")
        
        # 음성 이름 추출
        if voice_profile and voice_profile.get("mode") == "radio_show":
            voice_name = f"{voice_profile.get('host1', {}).get('name', 'Achernar')}_{voice_profile.get('host2', {}).get('name', 'Charon')}"
        else:
            voice_name = voice_profile.get("name", "Achernar") if voice_profile else "Achernar"
        
        # 모드 레이블 추출 (영어 키 사용)
        from ..utils import get_mode_profile
        mode_profile = get_mode_profile(narrative_mode)
        mode_label = mode_profile.get("label", "").replace("/", "_").replace(" ", "_")
        
        language_code = "ko-KR" if language == "ko" else "en-US"
        
        # 출력 디렉토리 생성 (narrative_mode 키 전달)
        output_dir, folder_name = prepare_output_directory(
            audio_title, voice_name, language_code, mode_label, narrative_mode
        )
        
        # 출력 파일 경로 생성 (narrative_mode 키 전달)
        paths = build_output_paths(audio_title, voice_name, language_code, mode_label, narrative_mode)
        
        # 오디오 파일 복사
        final_audio_path_obj = Path(final_audio_path)
        audio_file_path_obj = Path(paths["audio_file"])
        
        # 디버그 로그 (개발용, 환경 변수로 제어)
        from ..config import DEBUG_LOG_ENABLED, DEBUG_LOG_PATH
        if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
            try:
                DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                    import json
                    log_entry = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "B",
                        "location": "audio_postprocess.py:audio_postprocess_node",
                        "message": "audio_postprocess copy file BEFORE",
                        "data": {
                            "final_audio_path": str(final_audio_path_obj),
                            "final_audio_path_exists": final_audio_path_obj.exists(),
                            "audio_file_path": str(audio_file_path_obj),
                            "audio_file_path_parent_exists": audio_file_path_obj.parent.exists()
                        },
                        "timestamp": int(time.time() * 1000)
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            except: 
                pass
        
        if final_audio_path_obj.exists():
            # 대상 디렉토리가 없으면 생성
            audio_file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # 절대 경로로 변환하여 복사
            src_path = str(final_audio_path_obj.resolve())
            dst_path = str(audio_file_path_obj.resolve())
            
            # 디버그 로그 (개발용)
            if DEBUG_LOG_ENABLED and DEBUG_LOG_PATH:
                try:
                    DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
                        import json
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "audio_postprocess.py:audio_postprocess_node",
                            "message": "audio_postprocess copy file paths",
                            "data": {
                                "src_path": src_path,
                                "dst_path": dst_path,
                                "src_exists": Path(src_path).exists(),
                                "dst_parent_exists": Path(dst_path).parent.exists()
                            },
                            "timestamp": int(time.time() * 1000)
                        }
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                except: 
                    pass
            
            shutil.copy2(src_path, dst_path)
            print(f"  ✓ Audio file saved: {dst_path}", flush=True)
            
            # MP3/M4B 메타데이터 및 커버 아트 추가
            try:
                print(f"  🎨 Adding metadata/cover art...", flush=True)
                
                # audio_metadata 추출
                audio_metadata = state.get("audio_metadata")

                # 커버 아트: 기존 cover_*.jpg 우선, 없으면 생성/변환하여 jpg 확보
                cover_jpg = ensure_cover_art_jpeg(output_dir, audio_title=audio_title, audio_metadata=audio_metadata, voice_name=voice_name)
                if cover_jpg and cover_jpg.exists():
                    print(f"  ✓ Cover art ready: {cover_jpg.name}", flush=True)
                else:
                    print(f"  ⚠ Warning: Cover art not available, continuing without cover", flush=True)
                
                # MP3 메타데이터 추가
                metadata_success = add_mp3_metadata(
                    mp3_path=str(dst_path),
                    audio_metadata=audio_metadata,
                    audio_title=audio_title,
                    voice_name=voice_name,
                    cover_art_path=str(cover_jpg) if cover_jpg and cover_jpg.exists() else None
                )
                
                if metadata_success:
                    print(f"  ✓ MP3 metadata and cover art added successfully", flush=True)
                else:
                    print(f"  ⚠ Warning: Failed to add MP3 metadata", flush=True)
                    
            except Exception as metadata_err:
                log_error(f"Failed to add metadata/cover art: {metadata_err}", context="audio_postprocess_node", exception=metadata_err)
                print(f"  ⚠ Warning: Failed to add metadata/cover art: {metadata_err}", flush=True)
                # 메타데이터 추가 실패해도 계속 진행

            # 추가 출력 위치(C:/audiiobook)에도 복사
            try:
                secondary_dir = ADDITIONAL_OUTPUT_ROOT / Path(folder_name)
                secondary_dir.mkdir(parents=True, exist_ok=True)
                secondary_dst = secondary_dir / audio_file_path_obj.name
                
                # 메타데이터가 추가된 파일을 복사
                shutil.copy2(dst_path, str(secondary_dst))
                print(f"  ✓ Audio file also saved: {secondary_dst}", flush=True)
                
                # 커버 아트도 복사
                if cover_jpg and Path(cover_jpg).exists():
                    try:
                        secondary_cover = secondary_dir / cover_jpg.name
                        shutil.copy2(str(cover_jpg), str(secondary_cover))
                    except Exception as cover_copy_err:
                        print(f"  ⚠ Warning: Failed to copy cover art to secondary location: {cover_copy_err}", flush=True)

                # m4b도 복사
                try:
                    m4b_path = audio_file_path_obj.with_suffix(".m4b")
                    if m4b_path.exists():
                        shutil.copy2(str(m4b_path), str(secondary_dir / m4b_path.name))
                except Exception as m4b_copy_err:
                    print(f"  ⚠ Warning: Failed to copy m4b to secondary location: {m4b_copy_err}", flush=True)
                        
            except Exception as copy_err:
                print(f"  ⚠ Warning: Failed to copy to additional output: {copy_err}", flush=True)
        else:
            print(f"  ⚠ Warning: Source audio file not found: {final_audio_path}", flush=True)
        
        # 스크립트 저장
        scripts = state.get("scripts", [])
        if scripts:
            scripts_sorted = sorted(scripts, key=lambda x: x.get("segment_id", 0))
            full_script = "\n\n".join([s.get("script", "") for s in scripts_sorted])
            
            with open(paths["refined_text"], "w", encoding="utf-8") as f:
                f.write(full_script)
            print(f"  ✓ Script saved: {paths['refined_text']}", flush=True)
        
        # 제목 저장
        if audio_title:
            with open(paths["audio_title"], "w", encoding="utf-8") as f:
                f.write(audio_title)
            print(f"  ✓ Title saved: {paths['audio_title']}", flush=True)
        
        # Showrunner 세그먼트 저장
        segments = state.get("segments", [])
        if segments:
            import json
            with open(paths["blueprint"], "w", encoding="utf-8") as f:
                json.dump(segments, f, ensure_ascii=False, indent=2)
            print(f"  ✓ Blueprint saved: {paths['blueprint']}", flush=True)
        
        # abstract_outline 사용 제거 (요구사항: abstract_outline 비활성화)
        
        # 원본 입력 파일 복사
        original_text = state.get("original_text", "")
        if original_text:
            input_file_path = output_dir / "input.txt"
            with open(input_file_path, "w", encoding="utf-8") as f:
                f.write(original_text)
        
        # 최근 실행 경로 저장
        save_latest_run_path(output_dir)
        
        # State 업데이트
        state["final_audio_path"] = str(paths["audio_file"])
        state["output_dir"] = str(output_dir)
        
        # 워크플로우 타이밍 완료
        duration = log_workflow_step_end("audio_postprocess", start_time)
        print(f"\n✓ All files saved to: {output_dir} (Duration: {duration:.1f}s)", flush=True)
        
        return state
        
    except Exception as e:
        error_info = {
            "node_name": "audio_postprocess",
            "error_message": str(e),
            "segment_id": None
        }
        state["errors"].append(error_info)
        log_error(f"Audio postprocess node error: {e}", context="audio_postprocess_node", exception=e)
        print(f"Audio postprocess node error: {e}", flush=True)
        return state

