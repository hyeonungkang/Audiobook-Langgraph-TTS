"""
Text Service for text processing
텍스트 처리 함수들을 클래스로 통합
"""
from typing import Dict, Any, List, Optional, Tuple


class TextService:
    """
    텍스트 처리 관련 기능을 통합한 서비스 클래스
    """
    
    def validate_segments_quality(
        self,
        segments: List[Dict[str, Any]],
        language: str = "ko",
        min_core_length: int = 10
    ) -> Tuple[bool, List[str]]:
        """
        세그먼트 품질을 검증합니다.
        
        Args:
            segments: 세그먼트 리스트
            language: 언어 코드
            min_core_length: core_content 최소 길이
        
        Returns:
            (is_valid, error_messages)
        """
        errors: List[str] = []

        if not segments:
            return False, ["segments가 비어 있습니다"]

        placeholder_phrases = [
            "내용을 채워주세요",
            "내용을 채워 주세요",
            "please fill in content",
            "fill in content",
        ]

        # 필수 필드 및 플레이스홀더 검증
        for idx, seg in enumerate(segments):
            seg_id = seg.get("segment_id", idx + 1)
            required_fields = ["title", "core_content", "instruction_for_writer", "opening_line", "closing_line"]

            for field in required_fields:
                value = (seg.get(field) or "").strip()
                if not value:
                    errors.append(f"segment {seg_id}: {field} is empty")

            core_content = (seg.get("core_content") or "").strip()
            if core_content and len(core_content) < min_core_length:
                errors.append(f"segment {seg_id}: core_content too short (<{min_core_length})")

            lower_values = [
                (seg.get("title") or "").lower(),
                core_content.lower(),
                (seg.get("opening_line") or "").lower(),
                (seg.get("closing_line") or "").lower(),
                (seg.get("instruction_for_writer") or "").lower(),
            ]
            for phrase in placeholder_phrases:
                if any(phrase in v for v in lower_values):
                    errors.append(f"segment {seg_id}: contains placeholder '{phrase}'")
                    break

        # 세그먼트 간 opening/closing 중복 검증
        for i in range(len(segments) - 1):
            closing = (segments[i].get("closing_line") or "").strip()
            opening_next = (segments[i + 1].get("opening_line") or "").strip()
            if closing and opening_next and closing == opening_next:
                errors.append(f"segment {segments[i].get('segment_id', i + 1)} -> {segments[i + 1].get('segment_id', i + 2)}: closing_line duplicates next opening_line")

        return len(errors) == 0, errors
    
    def build_showrunner_prompt(
        self,
        text: str,
        config: Dict[str, Any],
        previous_errors: Optional[List[str]] = None
    ) -> str:
        """
        Showrunner 프롬프트를 생성합니다.
        
        Args:
            text: 입력 텍스트
            config: 설정 딕셔너리
            previous_errors: 이전 시도에서 발견된 문제 목록
        
        Returns:
            Showrunner 프롬프트 문자열
        """
        # TODO: utils.py의 build_showrunner_prompt 함수를 여기로 이동
        from ..utils import build_showrunner_prompt
        return build_showrunner_prompt(text, config, previous_errors)
    
    def build_writer_prompt(
        self,
        segment_info: Dict[str, Any],
        full_text: str,
        config: Dict[str, Any]
    ) -> str:
        """
        Writer 프롬프트를 생성합니다.
        
        Args:
            segment_info: 세그먼트 정보 딕셔너리
            full_text: 전체 텍스트
            config: 설정 딕셔너리
        
        Returns:
            Writer 프롬프트 문자열
        """
        # TODO: utils.py의 build_writer_prompt 함수를 여기로 이동
        from ..utils import build_writer_prompt
        return build_writer_prompt(segment_info, full_text, config)
    
    def sanitize_path_component(self, text: str) -> str:
        """
        경로 컴포넌트로 사용할 수 있도록 텍스트를 정리합니다.
        
        Args:
            text: 정리할 텍스트
        
        Returns:
            정리된 텍스트
        """
        # TODO: utils.py의 sanitize_path_component 함수를 여기로 이동
        from ..utils import sanitize_path_component
        return sanitize_path_component(text)
