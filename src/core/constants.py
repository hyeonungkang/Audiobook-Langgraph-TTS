"""
Constants for TTS Audiobook Converter
모든 매직 넘버와 문자열 상수를 중앙 집중식으로 관리
"""

# TTS Rate Limiting
TTS_QUOTA_RPM: float = 9.0  # 분당 9개로 운용 (안전 마진 포함)
TTS_ASSUMED_LATENCY_SEC: float = 15.0  # 1청크 평균 소요 시간
TTS_MAX_CONCURRENCY: int = 2  # 최대 동시 요청 수 (더 이상 사용 안 함)

# TTS API 제한
TTS_MAX_BYTES: int = 4000  # Gemini-TTS 최대 입력 바이트 수
TTS_SAFETY_MARGIN: int = 200  # 안전 마진 (바이트)
TTS_SAMPLE_RATE: int = 24000  # 기본 샘플 레이트 (Hz)

# TTS 배치 처리
TTS_BATCH_SIZE: int = 9  # 기본 배치 크기

# 서사 모드 기본값
DEFAULT_NARRATIVE_MODE: str = "mentor"

# 오디오 처리
AUDIO_BITRATE: str = "128k"  # 오디오 비트레이트
AUDIO_CODEC: str = "aac"  # 오디오 코덱

# 파일 확장자
EXT_MP3: str = ".mp3"
EXT_M4B: str = ".m4b"
EXT_JPEG: str = ".jpg"
EXT_PNG: str = ".png"

# 디렉토리 이름
DIR_TEMP_OUTPUT: str = "temp_output"
DIR_OUTPUTS: str = "outputs"

# 재시도 설정
MAX_RETRIES: int = 5  # 최대 재시도 횟수
INITIAL_RETRY_DELAY: float = 1.0  # 초기 재시도 대기 시간 (초)
RATE_LIMIT_BASE_WAIT: float = 60.0  # Rate limit 대기 시간 (초)

# 워크플로우 타이밍
TIMING_LOG_DIR: str = "logs"
TIMING_LOG_PREFIX: str = "workflow_timing_"

# 에러 로깅
ERROR_LOG_FILE: str = "error_log.txt"

# 텍스트 처리
MAX_SHOWRUNNER_INPUT_LENGTH: int = 50000  # Showrunner 최대 입력 길이
MIN_CORE_CONTENT_LENGTH: int = 10  # 최소 핵심 내용 길이

# 언어 코드
LANG_KO: str = "ko"
LANG_EN: str = "en"
LANG_KO_FULL: str = "ko-KR"
LANG_EN_FULL: str = "en-US"

# Gemini 모델
GEMINI_MODEL_PRO: str = "gemini-2.5-pro"
GEMINI_MODEL_FLASH: str = "gemini-2.5-flash"
GEMINI_MODEL_FLASH_LITE: str = "gemini-2.5-flash-lite"
GEMINI_TTS_MODEL_PRO: str = "gemini-2.5-pro-tts"
GEMINI_TTS_MODEL_FLASH: str = "gemini-2.5-flash-preview-tts"

# TTS 백엔드
TTS_BACKEND_CLOUD: str = "cloud"
TTS_BACKEND_GENAI: str = "genai"

# 서사 모드 키
NARRATIVE_MODE_MENTOR: str = "mentor"
NARRATIVE_MODE_LOVER: str = "lover"
NARRATIVE_MODE_FRIEND: str = "friend"
NARRATIVE_MODE_RADIO_SHOW: str = "radio_show"

# 콘텐츠 카테고리
CONTENT_CATEGORY_RESEARCH_PAPER: str = "research_paper"
CONTENT_CATEGORY_CAREER: str = "career"
CONTENT_CATEGORY_LANGUAGE_LEARNING: str = "language_learning"
CONTENT_CATEGORY_PHILOSOPHY: str = "philosophy"
CONTENT_CATEGORY_TECH_NEWS: str = "tech_news"
