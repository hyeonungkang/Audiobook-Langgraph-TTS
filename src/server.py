"""
FastAPI Server for TTS Audiobook Converter
프론트엔드와 통신하는 REST API 서버
"""
import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
from fastapi import UploadFile, File


# src 모듈 import를 위한 경로 설정
current_dir = Path(__file__).parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from src.job_manager import job_manager
from src.config import initialize_api_keys, application_path, OUTPUT_ROOT


# Pydantic 모델
class ConversionRequest(BaseModel):
    text: str
    config: Dict[str, Any]


class ConversionResponse(BaseModel):
    job_id: str
    status: str


# FastAPI 앱 생성
app = FastAPI(
    title="LangGraph TTS Converter API",
    description="AI-powered Text-to-Speech Audiobook Converter",
    version="1.0.0"
)

# CORS 설정 (개발 모드와 프로덕션 모드 모두 지원)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 로깅 미들웨어
@app.middleware("http")
async def log_requests(request, call_next):
    import time
    start_time = time.time()
    
    # 요청 로깅
    print(f"\n[API Request] {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        
        # 응답 로깅
        process_time = (time.time() - start_time) * 1000
        print(f"[API Response] {response.status_code} ({process_time:.2f}ms)")
        
        return response
    except Exception as e:
        print(f"[API Error] {str(e)}")
        raise


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    print("="*70)
    print("TTS Audiobook Converter API Server Starting...")
    print("="*70)
    
    # API 키 초기화 및 검증
    try:
        from src.config import validate_api_key
        
        api_key, _ = initialize_api_keys()
        
        if api_key:
            print("✓ API key loaded from configuration")
            
            # API 키 검증
            is_valid, message = validate_api_key(api_key)
            if is_valid:
                print(f"✓ API key validated successfully: {message}")
            else:
                print(f"✗ API key validation failed: {message}")
                print(f"  ⚠ TTS conversion will fail until valid API key is configured")
                print(f"  💡 Update your API key via: POST /api/v1/config")
        else:
            print("✗ No API key configured")
            print("  ⚠ TTS conversion requires a valid Google API key")
            print("  💡 Configure your API key via: POST /api/v1/config")
            
    except Exception as e:
        print(f"✗ API key initialization error: {e}")
        print("  ⚠ TTS conversion may not work correctly")
    
    print("✓ Server ready to accept requests")
    print("="*70)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "LangGraph TTS Converter API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy"}


@app.post("/api/v1/convert", response_model=ConversionResponse)
async def start_conversion(request: ConversionRequest):
    """
    TTS 변환 작업 시작
    
    Args:
        request: ConversionRequest
            - text: 변환할 텍스트
            - config: 설정 딕셔너리
                - language: 언어 (ko/en)
                - category: 콘텐츠 카테고리
                - narrative_mode: 서사 모드
                - voice: 음성 ID
                - host1_voice: 라디오쇼 모드 - 호스트1 음성 (선택)
                - host2_voice: 라디오쇼 모드 - 호스트2 음성 (선택)
                - listener_name: 청자 이름 (선택)
    
    Returns:
        ConversionResponse: job_id와 status 포함
    """
    try:
        # 입력 검증
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        if not request.config:
            raise HTTPException(status_code=400, detail="Config is required")
        
        # 필수 설정 확인
        required_fields = ["language", "category", "narrative_mode"]
        for field in required_fields:
            if field not in request.config:
                raise HTTPException(status_code=400, detail=f"Missing required config field: {field}")
        
        # 설정 빌드 (CLI와 동일한 로직으로 확장)
        from src.config_builder import build_config
        full_config = build_config(request.config)
        
        # 작업 생성
        job_id = job_manager.create_job(request.text, full_config)
        
        return ConversionResponse(
            job_id=job_id,
            status="processing"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/convert/{job_id}/status")
async def get_conversion_status(job_id: str):
    """
    작업 진행 상태 조회
    
    Args:
        job_id: 작업 ID
    
    Returns:
        작업 상태 딕셔너리
    """
    status = job_manager.get_job_status(job_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return status


@app.get("/api/v1/outputs/{filename}")
async def download_output(filename: str):
    """
    생성된 오디오 파일 다운로드
    
    Args:
        filename: 파일명
    
    Returns:
        FileResponse
    """
    # 보안: 경로 탈출 방지
    filename = Path(filename).name
    
    # outputs 폴더에서 파일 검색
    file_path = None
    for root, dirs, files in os.walk(OUTPUT_ROOT):
        if filename in files:
            file_path = Path(root) / filename
            break
    
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        media_type="audio/mpeg",
        filename=filename
    )


@app.get("/api/v1/voices")
async def get_available_voices():
    """
    사용 가능한 음성 목록 조회
    
    Returns:
        음성 목록
    """
    from src.utils import VOICE_BANKS
    
    voices = []
    for gender, bank in VOICE_BANKS.items():
        for voice in bank.get("voices", []):
            voices.append({
                "id": voice["name"],
                "name": voice["display"],
                "gender": gender,
                "description": bank.get("description", "")
            })
    
    return {"voices": voices}


@app.get("/api/v1/modes")
async def get_narrative_modes():
    """
    사용 가능한 서사 모드 목록 조회
    
    Returns:
        서사 모드 목록
    """
    from src.utils import NARRATIVE_MODES
    
    modes = []
    for mode_id, mode_data in NARRATIVE_MODES.items():
        modes.append({
            "id": mode_id,
            "label": mode_data.get("label", ""),
            "description": mode_data.get("description", "")
        })
    
    return {"modes": modes}


@app.get("/api/v1/config")
async def get_config():
    """
    현재 설정 조회 (민감한 정보 마스킹)
    """
    from src.config import load_config, CONFIG_PATH
    config = load_config()
    
    # 마스킹 처리
    if config.get("GOOGLE_API_KEY"):
        key = config["GOOGLE_API_KEY"]
        if len(key) > 8:
            config["GOOGLE_API_KEY"] = key[:4] + "*" * (len(key) - 8) + key[-4:]
        else:
            config["GOOGLE_API_KEY"] = "*" * len(key)
    
    # 설정 파일 경로 포함
    config["_config_path"] = str(CONFIG_PATH)
            
    return config


class ConfigUpdateRequest(BaseModel):
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    USER_NAME: Optional[str] = None
    MODEL_NAME: Optional[str] = None


@app.post("/api/v1/config")
async def update_config(request: ConfigUpdateRequest):
    """
    설정 업데이트
    """
    from src.config import load_config, save_config, initialize_api_keys, validate_api_key, CONFIG_PATH
    
    current_config = load_config()
    
    # API 키가 업데이트되면 검증
    if request.GOOGLE_API_KEY:
        # 새 API 키 검증
        is_valid, message = validate_api_key(request.GOOGLE_API_KEY)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid API key: {message}")
        
        current_config["GOOGLE_API_KEY"] = request.GOOGLE_API_KEY
        
    if request.GOOGLE_APPLICATION_CREDENTIALS is not None:
        current_config["GOOGLE_APPLICATION_CREDENTIALS"] = request.GOOGLE_APPLICATION_CREDENTIALS
        
    if request.USER_NAME:
        current_config["USER_NAME"] = request.USER_NAME
        
    if request.MODEL_NAME:
        current_config["MODEL_NAME"] = request.MODEL_NAME
    
    # 설정 저장
    try:
        saved_path = save_config(current_config)
        
        # 설정 적용을 위해 API 키 재초기화
        initialize_api_keys()
        
        return {
            "status": "success",
            "message": "Configuration updated and API key validated successfully",
            "config_path": saved_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")


@app.post("/api/v1/config/upload")
async def upload_config(file: UploadFile = File(...)):
    """
    설정 파일(config.json) 업로드 및 적용
    """
    from src.config import save_config, initialize_api_keys, validate_api_key
    import json
    
    try:
        content = await file.read()
        config_data = json.loads(content.decode("utf-8"))
        
        # 기본 검증
        if not isinstance(config_data, dict):
            raise HTTPException(status_code=400, detail="Invalid JSON format: Root must be a dictionary")
            
        # API 키 검증 (만약 포함되어 있다면)
        if "GOOGLE_API_KEY" in config_data:
            is_valid, message = validate_api_key(config_data["GOOGLE_API_KEY"])
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid API key in config file: {message}")
        
        # 설정 저장
        saved_path = save_config(config_data)
        
        # 설정 적용
        initialize_api_keys()
        
        return {
            "status": "success",
            "message": "Configuration uploaded and applied successfully",
            "config_path": saved_path
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process config file: {str(e)}")



@app.post("/api/v1/config/validate")
async def validate_config_api():
    """
    현재 저장된 API 키 검증
    """
    from src.config import load_config, validate_api_key
    import os
    
    # 환경 변수 또는 config.json에서 API 키 로드
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        config = load_config()
        api_key = config.get("GOOGLE_API_KEY")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured. Please add your API key first.")
    
    is_valid, message = validate_api_key(api_key)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail=message)
    
    return {"status": "valid", "message": message}


class OpenFolderRequest(BaseModel):
    path_type: str  # 'outputs' or 'logs'


@app.post("/api/v1/open-folder")
async def open_folder(request: OpenFolderRequest):
    """
    로컬 폴더 열기
    """
    import platform
    import subprocess
    from src.config import OUTPUT_ROOT, application_path
    
    target_path = None
    if request.path_type == "outputs":
        target_path = OUTPUT_ROOT
    elif request.path_type == "logs":
        target_path = application_path / "logs"
        target_path.mkdir(exist_ok=True)
        
    if not target_path:
        raise HTTPException(status_code=404, detail="Invalid folder type")
        
    # 폴더가 없으면 생성 시도
    if not target_path.exists():
        try:
            target_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create folder: {str(e)}")
            
    print(f"📂 Opening folder: {target_path}")

        
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(target_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", str(target_path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(target_path)])
            
        return {"status": "success", "message": f"Opened {request.path_type} folder"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {str(e)}")


def main():
    """서버 실행"""
    # 포트 설정 (환경변수 또는 기본값)
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    # 서버 실행
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()

