"""
Audio Service for audio processing
오디오 처리 함수들을 클래스로 통합
"""
from pathlib import Path
from typing import Dict, Any, Optional


class AudioService:
    """
    오디오 처리 관련 기능을 통합한 서비스 클래스
    """
    
    def add_m4b_metadata(
        self,
        m4b_path: Path,
        audio_metadata: Dict[str, Any],
        audio_title: str,
        voice_name: str,
        cover_art_path: Optional[Path] = None,
        ffmetadata_path: Optional[Path] = None,
    ) -> bool:
        """
        M4B 파일에 메타데이터를 추가합니다.
        
        Args:
            m4b_path: M4B 파일 경로
            audio_metadata: 오디오 메타데이터
            audio_title: 오디오 제목
            voice_name: 음성 이름
            cover_art_path: 커버 아트 경로
            ffmetadata_path: FFmetadata 파일 경로
        
        Returns:
            성공 여부
        """
        # TODO: utils.py의 add_m4b_metadata 함수를 여기로 이동
        from ..utils import add_m4b_metadata
        return add_m4b_metadata(
            m4b_path, audio_metadata, audio_title, voice_name,
            cover_art_path, ffmetadata_path
        )
    
    def build_ffmpeg_m4b_with_metadata(
        self,
        input_audio_path: Path,
        output_m4b_path: Path,
        audio_metadata: Dict[str, Any],
        audio_title: str,
        voice_name: str,
        cover_path: Optional[Path] = None,
        ffmetadata_path: Optional[Path] = None,
    ) -> bool:
        """
        FFmpeg를 사용하여 M4B 파일을 생성하고 메타데이터를 추가합니다.
        
        Args:
            input_audio_path: 입력 오디오 파일 경로
            output_m4b_path: 출력 M4B 파일 경로
            audio_metadata: 오디오 메타데이터
            audio_title: 오디오 제목
            voice_name: 음성 이름
            cover_path: 커버 아트 경로
            ffmetadata_path: FFmetadata 파일 경로
        
        Returns:
            성공 여부
        """
        # TODO: utils.py의 build_ffmpeg_m4b_with_metadata 함수를 여기로 이동
        from ..utils import build_ffmpeg_m4b_with_metadata
        return build_ffmpeg_m4b_with_metadata(
            input_audio_path, output_m4b_path, audio_metadata, audio_title,
            voice_name, cover_path, ffmetadata_path
        )
