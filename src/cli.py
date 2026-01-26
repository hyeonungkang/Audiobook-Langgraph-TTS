"""
Command-line interface functions for user interaction
Rich-based implementation for backward compatibility
"""
# Rich 기반 구현으로 전환 - 하위 호환성을 위해 기존 함수 시그니처 유지
from .cli.interactive import (
    select_content_category,
    select_language,
    select_narrative_mode,
    select_voice,
    select_radio_show_hosts,
    select_gemini_model,
)

# 새로운 모듈 구조에서 직접 import
from .models import NARRATIVE_MODES, DEFAULT_NARRATIVE_MODE, VOICE_BANKS, CONTENT_CATEGORIES
from .config import application_path

# 기존 함수들은 Rich 버전을 사용하도록 재내보냄
__all__ = [
    "select_content_category",
    "select_language",
    "select_narrative_mode",
    "select_voice",
    "select_radio_show_hosts",
    "select_gemini_model",
]
