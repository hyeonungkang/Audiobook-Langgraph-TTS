"""
Data models and metadata for TTS Audiobook Converter
"""
from .voice import VOICE_BANKS
from .narrative import DEFAULT_NARRATIVE_MODE, NARRATIVE_MODES
from .content import CONTENT_CATEGORIES

__all__ = [
    "VOICE_BANKS",
    "NARRATIVE_MODES",
    "DEFAULT_NARRATIVE_MODE",
    "CONTENT_CATEGORIES",
]
