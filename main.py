"""
TTS 오디오북 변환기 - Entry Point
이 파일은 단순 래퍼이며, 실제 로직은 src/main.py에 있습니다.
"""
import sys
import json
import time
import os
from pathlib import Path

# #region agent log
LOG_PATH = Path(__file__).parent / ".cursor" / "debug.log"
def _log_debug(location, message, data=None, hypothesis_id=None):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            entry = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": hypothesis_id or "A",
                "location": location,
                "message": message,
                "data": data or {},
                "timestamp": int(time.time() * 1000)
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except:
        pass
# #endregion

# src 모듈을 import할 수 있도록 경로 추가
if __name__ == "__main__":
    _log_debug("main.py:9", "Entry point reached", {"__name__": __name__}, "A")
    
    # 현재 디렉토리를 sys.path에 추가
    current_dir = Path(__file__).parent
    _log_debug("main.py:13", "Current directory set", {"current_dir": str(current_dir)}, "A")
    
    # 가상환경 자동 감지 및 활성화
    venv_paths = [
        current_dir / ".venv",
        current_dir / "venv",
        current_dir.parent / ".venv",
        current_dir.parent / "venv",
    ]
    
    venv_found = None
    for venv_path in venv_paths:
        if venv_path.exists():
            venv_found = venv_path
            _log_debug("main.py:25", "Virtual environment found", {"venv_path": str(venv_path)}, "A")
            break
    
    if venv_found:
        # Windows: .venv\Lib\site-packages, Linux/Mac: .venv/lib/pythonX.X/site-packages
        if sys.platform == "win32":
            venv_site_packages = venv_found / "Lib" / "site-packages"
            venv_scripts = venv_found / "Scripts"
            venv_python = venv_found / "Scripts" / "python.exe"
        else:
            venv_site_packages = venv_found / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
            venv_scripts = venv_found / "bin"
            venv_python = venv_found / "bin" / "python"
        
        # 가상환경 Python 인터프리터 확인
        if venv_python.exists():
            print(f"✓ Virtual environment detected: {venv_found}", flush=True)
            print(f"  Using venv Python: {venv_python}", flush=True)
        else:
            print(f"⚠ Virtual environment found but Python not at expected path: {venv_python}", flush=True)
        
        # site-packages를 sys.path에 추가 (가상환경의 패키지 우선 사용)
        if venv_site_packages.exists():
            if str(venv_site_packages) not in sys.path:
                sys.path.insert(0, str(venv_site_packages))
                _log_debug("main.py:38", "Added venv site-packages to sys.path", {"path": str(venv_site_packages)}, "A")
                print(f"  ✓ Added venv site-packages to Python path", flush=True)
            else:
                print(f"  ✓ Venv site-packages already in Python path", flush=True)
        else:
            print(f"  ⚠ Venv site-packages not found at: {venv_site_packages}", flush=True)
        
        # 환경 변수에 가상환경 경로 추가
        os.environ["VIRTUAL_ENV"] = str(venv_found)
        if str(venv_scripts) not in os.environ.get("PATH", ""):
            os.environ["PATH"] = str(venv_scripts) + os.pathsep + os.environ.get("PATH", "")
            _log_debug("main.py:44", "Updated PATH with venv scripts", {"venv_scripts": str(venv_scripts)}, "A")
            print(f"  ✓ Updated PATH with venv scripts", flush=True)
        
        # 현재 사용 중인 Python 경로 확인
        current_python = sys.executable
        if str(venv_python) in current_python or str(venv_found) in current_python:
            print(f"  ✓ Running with venv Python interpreter", flush=True)
        else:
            print(f"  ⚠ Not using venv Python interpreter, restarting with venv Python...", flush=True)
            print(f"    Current Python: {current_python}", flush=True)
            print(f"    Switching to: {venv_python}", flush=True)
            
            # 가상환경 Python으로 재시작
            import subprocess
            try:
                # 현재 스크립트 경로와 인자 전달
                script_path = Path(__file__).resolve()
                args = [str(venv_python), str(script_path)] + sys.argv[1:]
                
                # 재시작
                subprocess.run(args, check=False)
                sys.exit(0)
            except Exception as e:
                print(f"  ✗ Failed to restart with venv Python: {e}", flush=True)
                print(f"  Please run manually: {venv_python} main.py", flush=True)
                # 실패해도 계속 진행 (sys.path에 이미 추가했으므로)
    else:
        _log_debug("main.py:46", "No virtual environment found", {"checked_paths": [str(p) for p in venv_paths]}, "A")
        print("⚠ No virtual environment found. Using system Python.", flush=True)
        print(f"  Checked paths: {[str(p) for p in venv_paths]}", flush=True)
    
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
        _log_debug("main.py:50", "Added to sys.path", {"path": str(current_dir)}, "A")
    
    _log_debug("main.py:18", "Before import src.main", {"sys.path": sys.path[:3]}, "A")
    
    # src 모듈 존재 확인
    src_path = current_dir / "src"
    _log_debug("main.py:20", "Checking src directory", {"src_path": str(src_path), "exists": src_path.exists()}, "A")
    
    if not src_path.exists():
        _log_debug("main.py:22", "src directory not found", {"current_dir": str(current_dir)}, "A")
        print(f"✗ Error: src directory not found at {src_path}", flush=True)
        try:
            input("\nPress Enter to continue...")
        except:
            pass
        sys.exit(1)
    
    # src/main.py 파일 확인
    main_py_path = src_path / "main.py"
    _log_debug("main.py:30", "Checking src/main.py", {"main_py_path": str(main_py_path), "exists": main_py_path.exists()}, "A")
    
    if not main_py_path.exists():
        _log_debug("main.py:32", "src/main.py not found", {}, "A")
        print(f"✗ Error: src/main.py not found at {main_py_path}", flush=True)
        try:
            input("\nPress Enter to continue...")
        except:
            pass
        sys.exit(1)
    
    _log_debug("main.py:40", "Attempting import", {}, "A")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("src.main", main_py_path)
        _log_debug("main.py:43", "Module spec created", {"spec": str(spec)}, "A")
        
        if spec is None or spec.loader is None:
            _log_debug("main.py:45", "Failed to create module spec", {}, "A")
            raise ImportError("Failed to create module spec for src.main")
        
        module = importlib.util.module_from_spec(spec)
        _log_debug("main.py:49", "Module object created", {}, "A")
        
        sys.modules['src.main'] = module
        _log_debug("main.py:51", "Module added to sys.modules", {}, "A")
        
        _log_debug("main.py:53", "Before exec_module", {}, "A")
        try:
            spec.loader.exec_module(module)
            _log_debug("main.py:55", "Module executed successfully", {}, "A")
        except ImportError as import_err:
            _log_debug("main.py:57", "ImportError during module execution", {"error": str(import_err), "type": type(import_err).__name__}, "A")
            import traceback
            tb_str = traceback.format_exc()
            _log_debug("main.py:60", "ImportError traceback", {"traceback": tb_str}, "A")
            print(f"✗ Import error during module execution: {import_err}", flush=True)
            print(tb_str, flush=True)
            try:
                input("\nPress Enter to continue...")
            except:
                pass
            sys.exit(1)
        except Exception as exec_err:
            _log_debug("main.py:69", "Exception during module execution", {"error": str(exec_err), "type": type(exec_err).__name__}, "A")
            import traceback
            tb_str = traceback.format_exc()
            _log_debug("main.py:72", "Exception traceback", {"traceback": tb_str}, "A")
            print(f"✗ Error during module execution: {exec_err}", flush=True)
            print(tb_str, flush=True)
            try:
                input("\nPress Enter to continue...")
            except:
                pass
            raise
        
        try:
            main = module.main
            _log_debug("main.py:63", "main function extracted", {"main_type": str(type(main))}, "A")
        except AttributeError as attr_err:
            _log_debug("main.py:65", "main function not found in module", {"error": str(attr_err), "module_dir": dir(module)[:10]}, "A")
            raise
        
    except Exception as import_err:
        _log_debug("main.py:57", "Import failed", {"error": str(import_err), "type": type(import_err).__name__}, "A")
        import traceback
        tb_str = traceback.format_exc()
        _log_debug("main.py:60", "Traceback", {"traceback": tb_str}, "A")
        print(f"✗ Import error: {import_err}", flush=True)
        print(tb_str, flush=True)
        try:
            input("\nPress Enter to continue...")
        except:
            pass
        sys.exit(1)
    
    try:
        _log_debug("main.py:32", "Calling main()", {}, "A")
        print("Program starting...", flush=True)
        main()
        _log_debug("main.py:35", "main() returned", {}, "A")
        print("Program exited normally", flush=True)
    except KeyboardInterrupt:
        _log_debug("main.py:38", "KeyboardInterrupt", {}, "A")
        print("\nInterrupted by user.", flush=True)
        sys.exit(0)
    except Exception as e:
        _log_debug("main.py:42", "Exception in main()", {"error": str(e), "type": type(e).__name__}, "A")
        try:
            from src.utils import log_error
            log_error(f"Fatal error: {e}", context="main_entry")
        except:
            pass
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
