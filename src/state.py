"""
State definition for LangGraph TTS Audiobook Converter
"""
from typing import TypedDict, Optional


class AgentState(TypedDict):
    """State schema shared across the graph"""
    
    # Input
    original_text: str  # 원본 입력 텍스트
    
    # Configuration
    config: dict  # 사용자 설정 (content_category, language, narrative_mode, voice_profile, listener_name 등)
    
    # Showrunner output
    segments: list[dict]  # Showrunner가 생성한 15개 세그먼트 기획안
    audio_title: Optional[str]  # 오디오 제목
    
    # Writer output
    scripts: list[dict]  # Writer가 생성한 스크립트 (segment_id와 script 텍스트 포함)
    
    # TTS processing
    audio_chunks: list[str]  # TTS용 청킹된 텍스트 리스트
    audio_paths: list[str]  # 생성된 오디오 파일 경로 리스트
    
    # Final output
    final_audio_path: Optional[str]  # 최종 병합된 오디오 파일 경로
    output_dir: Optional[str]  # 최종 출력 디렉토리 경로
    
    # Error tracking
    errors: list[dict]  # 에러 로그 (segment_id, error_message, node_name 포함)

