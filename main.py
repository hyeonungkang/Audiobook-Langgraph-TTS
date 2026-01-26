"""
TTS 오디오북 변환기 - Entry Point
"""
import sys
import os
from pathlib import Path

# 현재 디렉토리를 sys.path에 추가
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# 가상환경 자동 감지 및 활성화
venv_paths = [
    current_dir / ".venv",
    current_dir / "venv",
]

venv_found = None
for venv_path in venv_paths:
    if venv_path.exists():
        venv_found = venv_path
        break

if venv_found:
    if sys.platform == "win32":
        venv_python = venv_found / "Scripts" / "python.exe"
        venv_site_packages = venv_found / "Lib" / "site-packages"
    else:
        venv_python = venv_found / "bin" / "python"
        venv_site_packages = venv_found / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    
    if venv_python.exists():
        # site-packages를 sys.path에 추가
        if venv_site_packages.exists() and str(venv_site_packages) not in sys.path:
            sys.path.insert(0, str(venv_site_packages))
        
        # 환경 변수 설정
        os.environ["VIRTUAL_ENV"] = str(venv_found)
        venv_scripts = venv_found / ("Scripts" if sys.platform == "win32" else "bin")
        if str(venv_scripts) not in os.environ.get("PATH", ""):
            os.environ["PATH"] = str(venv_scripts) + os.pathsep + os.environ.get("PATH", "")
        
        # 가상환경 Python으로 재시작 (필요한 경우)
        current_python = sys.executable
        if str(venv_python) not in current_python and str(venv_found) not in current_python:
            import subprocess
            script_path = Path(__file__).resolve()
            args = [str(venv_python), str(script_path)] + sys.argv[1:]
            subprocess.run(args, check=False)
            sys.exit(0)

# src/main.py import 및 실행
try:
    from src.main import main
    if __name__ == "__main__":
        main()
except KeyboardInterrupt:
    print("\nInterrupted by user.", flush=True)
    sys.exit(0)
except Exception as e:
    print(f"\n✗ Error: {e}", flush=True)
    import traceback
    traceback.print_exc()
    # 에러 발생 시 자동 종료 (사용자 입력 대기 없음)
    sys.exit(1)
