"""
Configuration management for TTS Audiobook Converter
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# Application path handling
if getattr(__import__('sys'), 'frozen', False):
    # PyInstaller로 빌드된 경우
    application_path = Path(__import__('sys').executable).parent
else:
    # 일반 Python 스크립트로 실행되는 경우
    application_path = Path(__file__).parent.parent

# 작업 디렉토리를 exe 파일 위치로 변경
os.chdir(application_path)

# ✅ config.json 경로 설정 (사용자 데이터 폴더)
if getattr(__import__('sys'), 'frozen', False):
    # 프로덕션: 사용자 데이터 폴더에 저장 (쓰기 권한 보장)
    try:
        import appdirs
        user_data_dir = Path(appdirs.user_data_dir("LangGraph-TTS", "LangGraph"))
        user_data_dir.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH = user_data_dir / "config.json"
        print(f"Using user data directory for config: {CONFIG_PATH}", flush=True)
    except Exception as e:
        print(f"Warning: Could not use appdirs, falling back to app directory: {e}", flush=True)
        CONFIG_PATH = application_path / "config.json"
else:
    # 개발 모드: 프로젝트 루트
    CONFIG_PATH = application_path / "config.json"

# 출력 폴더 및 최근 실행 경로 마커
OUTPUT_ROOT = application_path / "outputs"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# 추가 출력 폴더 (사용자 요청: C:\\audiiobook)
ADDITIONAL_OUTPUT_ROOT = Path("C:/audiiobook")
ADDITIONAL_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
LATEST_RUN_MARKER = application_path / "latest_run_path.txt"

# 디버그 로그 설정 (개발용, 프로덕션에서는 False로 설정)
DEBUG_LOG_ENABLED = os.getenv("DEBUG_LOG_ENABLED", "false").lower() == "true"
DEBUG_LOG_PATH = application_path / ".cursor" / "debug.log" if DEBUG_LOG_ENABLED else None

# 텍스트 처리 관련 상수
MAX_SHOWRUNNER_INPUT_LENGTH = 50000  # Showrunner 입력 텍스트 최대 길이 (bytes)
MAX_WRITER_INPUT_LENGTH = 30000  # Writer 입력 텍스트 최대 길이 (bytes)


def load_config():
    """config.json에서 설정 로드 (사용자 데이터 폴더 또는 앱 폴더)"""
    config = {}
    
    # CONFIG_PATH 사용 (사용자 데이터 폴더 또는 앱 폴더)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"✓ Config loaded from: {CONFIG_PATH}", flush=True)
        except Exception as e:
            print(f"✗ Failed to load config from {CONFIG_PATH}: {e}", flush=True)
    else:
        # 설정 파일이 없으면 기본값으로 생성
        print(f"ℹ Config file not found at {CONFIG_PATH}, creating with defaults", flush=True)
        config = {
            "USER_NAME": "용사",
            "MODEL_NAME": "gemini-2.5-pro"
        }
        # 기본 설정 저장 시도
        try:
            save_config(config)
        except Exception as e:
            print(f"⚠ Could not create default config: {e}", flush=True)
    
    # 기본값 확인
    if "USER_NAME" not in config:
        config["USER_NAME"] = "용사"
    if "MODEL_NAME" not in config:
        config["MODEL_NAME"] = "gemini-2.5-pro"
        
    return config


def save_config(config):
    """설정을 config.json에 저장 (사용자 데이터 폴더)"""
    try:
        # 디렉토리 생성 확인
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # 설정 저장
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Configuration saved to: {CONFIG_PATH}", flush=True)
        
        # win-unpacked 폴더에도 동기화 (배포된 앱을 위해)
        # 개발 환경에서 실행 중일 때, electron/dist/win-unpacked/config.json 에도 복사
        try:
            # 프로젝트 루트 찾기 (src의 부모)
            project_root = Path(__file__).parent.parent
            win_unpacked_config = project_root / "electron" / "dist" / "win-unpacked" / "config.json"
            
            if win_unpacked_config.parent.exists():
                with open(win_unpacked_config, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                print(f"✓ Configuration synced to: {win_unpacked_config}", flush=True)
        except Exception as e:
            # 동기화 실패는 치명적이지 않음
            print(f"⚠ Failed to sync config to win-unpacked: {e}", flush=True)
            
        return str(CONFIG_PATH)
        
    except Exception as e:
        error_msg = f"✗ Failed to save config to {CONFIG_PATH}: {e}"
        print(error_msg, flush=True)
        raise Exception(error_msg)


def load_latest_run_path() -> Path | None:
    """
    마지막 실행 출력 폴더 경로를 불러옵니다.
    """
    if not LATEST_RUN_MARKER.exists():
        return None
    try:
        with open(LATEST_RUN_MARKER, "r", encoding="utf-8") as f:
            path_str = f.read().strip()
        if not path_str:
            return None
        candidate = Path(path_str)
        if not candidate.is_absolute():
            candidate = application_path / candidate
        return candidate if candidate.exists() else None
    except Exception as e:
        print(f"  ⚠ Warning: Failed to read latest run marker ({e})", flush=True)
        return None


def set_system_environment_variable(var_name: str, var_value: str) -> bool:
    """
    시스템 환경 변수 설정 (Windows 전용)
    
    Args:
        var_name: 환경 변수 이름
        var_value: 환경 변수 값
    
    Returns:
        성공 여부
    """
    try:
        import winreg
        
        # 사용자 환경 변수 레지스트리 경로
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Environment',
            0,
            winreg.KEY_ALL_ACCESS
        )
        
        # 환경 변수 설정
        winreg.SetValueEx(key, var_name, 0, winreg.REG_SZ, var_value)
        winreg.CloseKey(key)
        
        # 현재 프로세스에도 즉시 적용
        os.environ[var_name] = var_value
        
        print(f"✓ System environment variable '{var_name}' set successfully", flush=True)
        return True
        
    except Exception as e:
        print(f"✗ Failed to set system environment variable: {e}", flush=True)
        # 실패해도 현재 프로세스에는 설정
        os.environ[var_name] = var_value
        return False


def prompt_api_key_input() -> str:
    """
    CLI에서 API 키 입력받기
    """
    print("\n" + "="*70)
    print("🔑 Google Gemini API Key Required")
    print("="*70)
    print("\n📋 API 키를 아직 설정하지 않으셨습니다.")
    print("\n💡 API 키 형식: AIza로 시작하는 39자 문자열")
    print("   예시: AIzaSyDaGmWKa4JsXZ-HjGw7ISLn55QdikrYKj0")
    print("\n🌐 API 키 생성 방법:")
    print("   1. https://makersuite.google.com/app/apikey 방문")
    print("   2. 'Create API Key' 클릭")
    print("   3. 생성된 키를 복사")
    print("\n" + "="*70)
    
    while True:
        api_key = input("\n🔐 Google Gemini API Key를 입력하세요: ").strip()
        
        if not api_key:
            print("❌ API 키가 비어있습니다. 다시 입력해주세요.")
            continue
        
        if not api_key.startswith("AIza"):
            print("⚠️  경고: API 키는 일반적으로 'AIza'로 시작합니다.")
            confirm = input("   그래도 계속하시겠습니까? (y/n): ").lower()
            if confirm != 'y':
                continue
        
        if len(api_key) < 30:
            print("⚠️  경고: API 키 길이가 너무 짧습니다 (일반적으로 39자).")
            confirm = input("   그래도 계속하시겠습니까? (y/n): ").lower()
            if confirm != 'y':
                continue
        
        return api_key


def save_env_file(key: str, value: str):
    """
    .env 파일에 환경 변수 저장 (한국어 주석 제거, 값만 저장)
    """
    env_path = application_path / '.env'
    
    # 기존 .env 파일 읽기 (주석 제거, 값만 저장)
    env_vars = {}
    if env_path.exists():
        try:
            with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    # 주석 제거 (한국어 주석 포함)
                    if '#' in line:
                        line = line.split('#')[0].strip()
                    # 빈 줄과 주석만 있는 줄 건너뛰기
                    if line and '=' in line:
                        k, v = line.split('=', 1)
                        env_vars[k.strip()] = v.strip()
        except Exception as e:
            print(f"Warning: Failed to read existing .env file: {e}", flush=True)
    
    # 새 값 업데이트
    env_vars[key] = value
    
    # .env 파일에 쓰기 (주석 없이 값만 저장)
    try:
        with open(env_path, 'w', encoding='utf-8', errors='ignore') as f:
            # 중요 환경 변수만 저장 (주석 없이)
            if 'GOOGLE_API_KEY' in env_vars:
                f.write(f"GOOGLE_API_KEY={env_vars['GOOGLE_API_KEY']}\n")
            if 'GOOGLE_APPLICATION_CREDENTIALS' in env_vars:
                f.write(f"GOOGLE_APPLICATION_CREDENTIALS={env_vars['GOOGLE_APPLICATION_CREDENTIALS']}\n")
        print(f"Saved {key} to .env file: {env_path}", flush=True)
        return True
    except Exception as e:
        print(f"Failed to save .env file: {e}", flush=True)
        return False


def initialize_api_keys():
    """
    API 키 초기화 - .env 파일 우선 (표준 방식)
    
    우선순위:
    1. .env 파일 (프로젝트 루트)
    2. 시스템 환경 변수 (GOOGLE_API_KEY)
    3. config.json (백업용, 하위 호환성)
    4. 사용자 입력 프롬프트
    """
    # #region agent log
    import json
    import time
    from pathlib import Path
    LOG_PATH = Path(__file__).parent.parent / ".cursor" / "debug.log"
    def _log(loc, msg, data=None, h="C"):
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":h,"location":loc,"message":msg,"data":data or {},"timestamp":int(time.time()*1000)}, ensure_ascii=False) + "\n")
        except:
            pass
    # #endregion
    
    _log("src/config.py:221", "initialize_api_keys() entry", {}, "C")
    
    print("="*70)
    print("🔑 API Key Initialization")
    print("="*70)
    
    _log("src/config.py:235", "Before checking .env file", {}, "C")
    # 1. .env 파일 확인 (최우선 - 표준 방식)
    env_path = application_path / '.env'
    _log("src/config.py:257", "Checking .env file", {"env_path": str(env_path), "exists": env_path.exists()}, "C")
    
    GOOGLE_API_KEY = None
    if env_path.exists():
        try:
            # .env 파일 직접 읽기 (한국어 주석 문제 방지)
            with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    # 주석 제거
                    if '#' in line:
                        line = line.split('#')[0].strip()
                    # KEY=value 형식만 처리
                    if line and '=' in line and line.startswith('GOOGLE_API_KEY='):
                        GOOGLE_API_KEY = line.split('=', 1)[1].strip()
                        break
            
            # dotenv로도 시도 (fallback)
            if not GOOGLE_API_KEY:
                load_dotenv(env_path)
                GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
            
            if GOOGLE_API_KEY:
                _log("src/config.py:262", "API key loaded from .env", {}, "C")
                print(f"API key loaded from .env file: {env_path}", flush=True)
        except Exception as e:
            _log("src/config.py:265", "Failed to load .env", {"error": str(e)}, "C")
    
    # 2. 시스템 환경 변수 확인 (차선)
    if not GOOGLE_API_KEY:
        _log("src/config.py:248", "No API key in .env, checking env var", {}, "C")
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        if GOOGLE_API_KEY:
            _log("src/config.py:251", "API key found in env var", {}, "C")
            print("✓ API key found in system environment variable", flush=True)
    
    # 3. config.json 확인 (백업용, 하위 호환성)
    if not GOOGLE_API_KEY:
        _log("src/config.py:235", "No API key in .env/env, checking config.json", {}, "C")
        try:
            config = load_config()
            _log("src/config.py:238", "load_config() succeeded", {"config_keys": list(config.keys())}, "C")
            GOOGLE_API_KEY = config.get("GOOGLE_API_KEY")
            if GOOGLE_API_KEY:
                _log("src/config.py:245", "API key found in config.json", {}, "C")
                print("✓ API key found in config.json (backward compatibility)", flush=True)
                # .env 파일로 마이그레이션
                print("💡 Migrating API key from config.json to .env file...", flush=True)
                save_env_file("GOOGLE_API_KEY", GOOGLE_API_KEY)
        except Exception as e:
            _log("src/config.py:240", "load_config() failed", {"error": str(e), "type": type(e).__name__}, "C")
    
    # 4. API 키가 없으면 사용자 입력 받기
    if not GOOGLE_API_KEY:
        _log("src/config.py:270", "No API key found, prompting user", {}, "C")
        print("✗ No API key found in any configuration", flush=True)
        print("💡 Starting interactive API key setup...", flush=True)
        
        try:
            GOOGLE_API_KEY = prompt_api_key_input()
            _log("src/config.py:276", "User provided API key", {"key_length": len(GOOGLE_API_KEY) if GOOGLE_API_KEY else 0}, "C")
        except Exception as e:
            _log("src/config.py:278", "prompt_api_key_input() failed", {"error": str(e), "type": type(e).__name__}, "C")
            raise
        
        # 입력받은 API 키를 .env 파일에 저장 (표준 방식)
        _log("src/config.py:282", "Saving API key to .env file", {}, "C")
        print("\n💾 Saving API key to .env file...", flush=True)
        try:
            save_env_file("GOOGLE_API_KEY", GOOGLE_API_KEY)
            _log("src/config.py:286", "save_env_file() succeeded", {}, "C")
        except Exception as e:
            _log("src/config.py:288", "save_env_file() failed", {"error": str(e)}, "C")
            # .env 저장 실패 시 config.json에 백업 저장 (하위 호환성)
            print("⚠️  Failed to save to .env, saving to config.json as backup...", flush=True)
            try:
                config = load_config()
                config["GOOGLE_API_KEY"] = GOOGLE_API_KEY
                save_config(config)
            except Exception as e2:
                print(f"✗ Failed to save to config.json as well: {e2}", flush=True)
                raise
    
    # ✅ API 키를 현재 프로세스 환경 변수에 설정 (global)
    _log("src/config.py:300", "Setting os.environ['GOOGLE_API_KEY']", {}, "C")
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
    print(f"\n✓ GOOGLE_API_KEY set: {GOOGLE_API_KEY[:10]}... (showing first 10 chars)", flush=True)
    
    # Gemini API 초기화
    # 타임아웃은 generate_content_with_retry 함수에서 처리됨
    _log("src/config.py:305", "Before genai.configure()", {}, "C")
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        _log("src/config.py:308", "genai.configure() succeeded", {}, "C")
        print("✓ Gemini API configured successfully", flush=True)
    except Exception as e:
        _log("src/config.py:311", "genai.configure() failed", {"error": str(e), "type": type(e).__name__}, "C")
        print(f"✗ Failed to configure Gemini API: {e}", flush=True)
        raise
    
    # 서비스 계정 키 파일 (TTS용)
    # .env 파일에서 먼저 확인
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not GOOGLE_APPLICATION_CREDENTIALS:
        # config.json에서 확인 (백업용)
        try:
            config = load_config()
            GOOGLE_APPLICATION_CREDENTIALS = config.get("GOOGLE_APPLICATION_CREDENTIALS") or ""
        except:
            GOOGLE_APPLICATION_CREDENTIALS = ""
    
    if GOOGLE_APPLICATION_CREDENTIALS:
        if not os.path.isabs(GOOGLE_APPLICATION_CREDENTIALS):
            key_path = application_path / GOOGLE_APPLICATION_CREDENTIALS
            GOOGLE_APPLICATION_CREDENTIALS = str(key_path)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
        print(f"✓ Service account key: {GOOGLE_APPLICATION_CREDENTIALS}", flush=True)
    else:
        print("⚠️  Service account key not configured (TTS may not work)", flush=True)
    
    _log("src/config.py:315", "initialize_api_keys() completed successfully", {}, "C")
    print(f"\n📂 Application path: {application_path}", flush=True)
    print("="*70 + "\n")
    
    return GOOGLE_API_KEY, GOOGLE_APPLICATION_CREDENTIALS


def validate_api_key(api_key: str) -> tuple[bool, str]:
    """
    Google Gemini API 키 검증
    
    Args:
        api_key: 검증할 API 키
    
    Returns:
        (is_valid: bool, message: str)
    """
    if not api_key or not api_key.strip():
        return False, "API key is empty"
    
    try:
        # API 키로 Gemini 설정
        genai.configure(api_key=api_key)
        
        # 간단한 테스트 요청 (최소 토큰)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(
            "test",
            generation_config={'max_output_tokens': 1}
        )
        
        # 응답이 있으면 성공
        if response:
            return True, "API key is valid"
        else:
            return False, "API key validation failed: No response"
            
    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "invalid" in error_msg.lower():
            return False, "Invalid API key"
        elif "quota" in error_msg.lower():
            return False, "API quota exceeded"
        elif "permission" in error_msg.lower():
            return False, "API key lacks required permissions"
        else:
            return False, f"API key validation error: {error_msg}"

