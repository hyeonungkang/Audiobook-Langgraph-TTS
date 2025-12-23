"""
Main entry point for TTS Audiobook Converter
"""
import sys
import time
import json
from pathlib import Path

# #region agent log
LOG_PATH = Path(__file__).parent.parent / ".cursor" / "debug.log"
def _log_import(loc, msg, data=None, h="D"):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":h,"location":loc,"message":msg,"data":data or {},"timestamp":int(time.time()*1000)}, ensure_ascii=False) + "\n")
    except:
        pass
# #endregion

_log_import("src/main.py:7", "Module import started", {}, "D")

# 출력 버퍼링 비활성화 (즉시 출력)
try:
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
    _log_import("src/main.py:20", "stdout reconfigured", {}, "D")
except Exception as e:
    _log_import("src/main.py:22", "stdout reconfigure failed", {"error": str(e)}, "D")

_log_import("src/main.py:24", "Before importing .cli", {}, "D")
try:
    from .cli import select_content_category, select_language, select_narrative_mode, select_voice, select_radio_show_hosts, select_gemini_model
    _log_import("src/main.py:26", ".cli import succeeded", {}, "D")
except Exception as e:
    _log_import("src/main.py:28", ".cli import failed", {"error": str(e), "type": type(e).__name__}, "D")
    raise
_log_import("src/main.py:30", "Before importing .utils", {}, "D")
try:
    from .utils import (
        get_mode_profile,
        get_tts_prompt_for_mode,
        get_listener_names,
        prompt_listener_name,
        PYDUB_AVAILABLE,
        log_error,
        save_workflow_timing_log,
        get_workflow_timing_summary,
        set_gemini_model,
    )
    _log_import("src/main.py:42", ".utils import succeeded", {}, "D")
except Exception as e:
    _log_import("src/main.py:44", ".utils import failed", {"error": str(e), "type": type(e).__name__}, "D")
    raise

_log_import("src/main.py:46", "Before importing .config", {}, "D")
try:
    from .config import application_path, load_latest_run_path, initialize_api_keys
    _log_import("src/main.py:48", ".config import succeeded", {}, "D")
except Exception as e:
    _log_import("src/main.py:50", ".config import failed", {"error": str(e), "type": type(e).__name__}, "D")
    raise

_log_import("src/main.py:52", "Before importing .graph", {}, "D")
try:
    from .graph import compile_graph
    _log_import("src/main.py:54", ".graph import succeeded", {}, "D")
except Exception as e:
    _log_import("src/main.py:56", ".graph import failed", {"error": str(e), "type": type(e).__name__}, "D")
    raise

_log_import("src/main.py:58", "Before importing .state", {}, "D")
try:
    from .state import AgentState
    _log_import("src/main.py:60", ".state import succeeded", {}, "D")
except Exception as e:
    _log_import("src/main.py:62", ".state import failed", {"error": str(e), "type": type(e).__name__}, "D")
    raise

_log_import("src/main.py:64", "All imports completed", {}, "D")


def main():
    """메인 실행 함수"""
    # #region agent log
    import json
    import time
    from pathlib import Path
    LOG_PATH = Path(__file__).parent.parent / ".cursor" / "debug.log"
    def _log(loc, msg, data=None, h="B"):
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":h,"location":loc,"message":msg,"data":data or {},"timestamp":int(time.time()*1000)}, ensure_ascii=False) + "\n")
        except:
            pass
    # #endregion
    
    _log("src/main.py:28", "main() entry", {}, "B")
    
    # API 키 초기화
    _log("src/main.py:31", "Before initialize_api_keys()", {}, "B")
    try:
        initialize_api_keys()
        _log("src/main.py:34", "initialize_api_keys() succeeded", {}, "B")
    except Exception as e:
        _log("src/main.py:36", "initialize_api_keys() failed", {"error": str(e), "type": type(e).__name__}, "B")
        log_error(f"API key initialization failed: {e}", context="main")
        print(f"✗ Error: API key initialization failed: {e}", flush=True)
        return
    
    _log("src/main.py:38", "After API init, setting up paths", {}, "B")
    start_time = time.time()
    input_file = application_path / "input.txt"
    _log("src/main.py:41", "input_file path set", {"input_file": str(input_file), "application_path": str(application_path)}, "B")
    latest_output_dir = load_latest_run_path()
    _log("src/main.py:43", "latest_output_dir loaded", {"latest_output_dir": str(latest_output_dir) if latest_output_dir else None}, "B")
    
    print("="*70, flush=True)
    print("TTS Audiobook Converter Starting", flush=True)
    print("="*70, flush=True)
    if latest_output_dir:
        print(f"  ℹ︎ Last run output folder: {latest_output_dir}", flush=True)
    
    print("\n" + "="*70, flush=True)
    print("📋 설정 단계 안내", flush=True)
    print("="*70, flush=True)
    print("다음 순서로 설정을 진행합니다:", flush=True)
    print("  1️⃣  Gemini 모델 선택 (Pro/Flash)", flush=True)
    print("  2️⃣  콘텐츠 카테고리 선택 (논문/커리어/어학/철학/뉴스)", flush=True)
    print("  3️⃣  언어 선택 (한국어/영어)", flush=True)
    print("  4️⃣  서사 모드 선택 (이성친구/친구/라디오쇼)", flush=True)
    print("  5️⃣  음성 선택 (모드에 따라 1개 또는 2개)", flush=True)
    print("  6️⃣  청취자 이름 입력", flush=True)
    print("="*70, flush=True)
    
    # 1단계: Gemini 모델 선택
    _log("src/main.py:64", "Before select_gemini_model()", {}, "B")
    print("\n" + "="*70, flush=True)
    print("1️⃣  Gemini 모델 선택", flush=True)
    print("="*70, flush=True)
    selected_model = select_gemini_model()
    _log("src/main.py:68", "After select_gemini_model()", {"selected_model": selected_model}, "B")
    set_gemini_model(selected_model)  # 전역 변수에 설정
    
    # 2단계: 콘텐츠 카테고리 선택
    print("\n" + "="*70, flush=True)
    print("2️⃣  콘텐츠 카테고리 선택", flush=True)
    print("="*70, flush=True)
    selected_category = select_content_category()
    
    # 3단계: 언어 선택
    print("\n" + "="*70, flush=True)
    print("3️⃣  언어 선택", flush=True)
    print("="*70, flush=True)
    selected_language = select_language()
    
    # 4단계: 서사 모드 선택
    print("\n" + "="*70, flush=True)
    print("4️⃣  서사 모드 선택", flush=True)
    print("="*70, flush=True)
    selected_mode = select_narrative_mode(category=selected_category)
    mode_profile = get_mode_profile(selected_mode)
    tts_prompt = get_tts_prompt_for_mode(mode_profile, selected_language)
    print(f"  ✓ Narrative style: {mode_profile['label']} ({mode_profile['description']})", flush=True)
    
    # 5단계: 음성 선택 (라디오쇼 모드는 두 개의 음성 필요)
    print("\n" + "="*70, flush=True)
    print("5️⃣  음성 선택", flush=True)
    print("="*70, flush=True)
    if selected_mode == "radio_show":
        print("  ℹ︎ 라디오쇼 모드: 첫 번째 화자와 두 번째 화자의 음성을 각각 선택합니다.", flush=True)
        print("  ℹ︎ 성별 제한 없이 자유롭게 선택할 수 있습니다 (예: 여자-여자, 남자-남자, 남자-여자 등).", flush=True)
        host1_voice, host2_voice = select_radio_show_hosts(language=selected_language)
        selected_voice = {
            "host1": host1_voice,
            "host2": host2_voice,
            "mode": "radio_show"
        }
        print(f"\n  ✓ Radio show voices: First Host = {host1_voice['display']}, Second Host = {host2_voice['display']}", flush=True)
    else:
        print("  ℹ︎ 단일 화자 모드: 하나의 음성을 선택합니다.", flush=True)
        selected_voice = select_voice(language=selected_language)
    
    # 6단계: 청취자 이름 입력
    print("\n" + "="*70, flush=True)
    print("6️⃣  청취자 이름 입력", flush=True)
    print("="*70, flush=True)
    listener_name = prompt_listener_name(default_name="용사")
    listener_names = get_listener_names(listener_name)
    listener_suffix = listener_names["suffix"]
    listener_base = listener_names["base"]
    print(f"  ✓ 한국어 대본에서는 '{listener_suffix}'를, 영어 대본에서는 '{listener_base}'를 사용할게요.", flush=True)
    
    # Normal flow: Read input.txt and process with Showrunner/Writer
    # Read input.txt
    try:
        print(f"\n[1/4] Reading input file: {input_file}", flush=True)
        sys.stdout.flush()
        if not input_file.exists():
            print(f"✗ Error: Input file not found: {input_file}", flush=True)
            return
        
        with open(input_file, "r", encoding="utf-8") as f:
            raw_text = f.read()
        
        if not raw_text.strip():
            print("Warning: input.txt file is empty.", flush=True)
            return
            
        print(f"  ✓ Input text length: {len(raw_text):,} characters", flush=True)
        print(f"  ✓ Input text bytes: {len(raw_text.encode('utf-8')):,} bytes", flush=True)
        sys.stdout.flush()
        
    except FileNotFoundError:
        log_error(f"Input file not found: {input_file}", context="main")
        print(f"✗ Error: Input file not found: {input_file}", flush=True)
        sys.stdout.flush()
        return
    except Exception as e:
        log_error(f"File read error: {e}", context="main")
        print(f"✗ File read error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return
    
    # LangGraph 실행
    print(f"\n[2/4] Processing with LangGraph pipeline...", flush=True)
    sys.stdout.flush()
    step_start = time.time()
    try:
        # 초기 State 생성
        initial_state: AgentState = {
            "original_text": raw_text,
            "config": {
                "gemini_model": selected_model,
                "content_category": selected_category,
                "language": selected_language,
                "narrative_mode": selected_mode,
                "voice_profile": selected_voice,
                "listener_name": listener_name
            },
            "segments": [],
            "scripts": [],
            "audio_chunks": [],
            "audio_paths": [],
            "final_audio_path": None,
            "audio_title": None,
            "output_dir": None,
            "errors": []
        }
        
        # 그래프 컴파일 및 실행
        app = compile_graph()
        
        print("  ✓ LangGraph compiled, starting execution...", flush=True)
        final_state = app.invoke(initial_state)
        
        step_time = time.time() - step_start
        print(f"  ✓ Completed (Time taken: {step_time:.1f} seconds)", flush=True)
        
        # 에러 확인
        errors = final_state.get("errors", [])
        if errors:
            print(f"  ⚠ Warning: {len(errors)} errors occurred during processing", flush=True)
            for error in errors:
                print(f"    - {error.get('node_name')}: {error.get('error_message')}", flush=True)
        
        # 결과 추출
        audio_title = final_state.get("audio_title", "output")
        final_audio_path = final_state.get("final_audio_path")
        segments = final_state.get("segments", [])
        output_dir = final_state.get("output_dir")
        
        print(f"  ✓ Audio title: {audio_title}", flush=True)
        if final_audio_path:
            print(f"  ✓ Final audio: {final_audio_path}", flush=True)
        
        sys.stdout.flush()
    except Exception as e:
        log_error(f"LangGraph execution failed: {e}", context="main")
        print(f"✗ LangGraph execution failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return
    
    # 워크플로우 타이밍 로그 저장
    timing_log_path = save_workflow_timing_log()
    if timing_log_path:
        print(f"\n  ✓ Workflow timing log saved: {timing_log_path}", flush=True)
    
    # 워크플로우 타이밍 요약 표시
    timing_summary = get_workflow_timing_summary()
    if timing_summary:
        print("\n" + "="*70, flush=True)
        print("📊 Workflow Timing Summary", flush=True)
        print("="*70, flush=True)
        for step_name, info in timing_summary.items():
            duration = info["duration_seconds"]
            print(f"  • {step_name:20s}: {duration:6.1f}s ({duration/60:.2f} min)", flush=True)
        print("="*70, flush=True)
    
    # Print total execution time and results
    total_time = time.time() - start_time
    print("\n" + "="*70, flush=True)
    print(f"✓ All tasks completed!", flush=True)
    print(f"  Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)", flush=True)
    if final_audio_path:
        print(f"  Output file: {final_audio_path}", flush=True)
        output_dir = Path(final_audio_path).parent
    if output_dir:
        print(f"  Output folder: {output_dir}", flush=True)
    print("="*70, flush=True)


if __name__ == "__main__":
    try:
        print("Program starting...", flush=True)
        main()
        print("Program exited normally", flush=True)
    except KeyboardInterrupt:
        print("\nInterrupted by user.", flush=True)
        sys.exit(0)
    except Exception as e:
        log_error(f"Fatal error: {e}", context="main_entry")
        print("\n" + "="*60, flush=True)
        print("An error occurred during program execution:", flush=True)
        print("="*60, flush=True)
        print(f"Error type: {type(e).__name__}", flush=True)
        print(f"Error message: {str(e)}", flush=True)
        print("="*60, flush=True)
        import traceback
        traceback.print_exc()
        try:
            input("\nPress Enter to continue...")
        except:
            pass
        raise

