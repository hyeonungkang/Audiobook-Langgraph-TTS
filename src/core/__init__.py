"""
Core modules for TTS Audiobook Converter
"""
from .constants import (
    TTS_QUOTA_RPM,
    TTS_ASSUMED_LATENCY_SEC,
    TTS_MAX_CONCURRENCY,
    TTS_MAX_BYTES,
    TTS_SAFETY_MARGIN,
    TTS_SAMPLE_RATE,
    TTS_BATCH_SIZE,
    DEFAULT_NARRATIVE_MODE,
)
from .rate_limiter import RateLimiter, get_default_rate_limiter, set_default_rate_limiter
from .error_handler import ErrorHandler
from .config_manager import ConfigManager, get_default_config_manager, set_default_config_manager

__all__ = [
    "RateLimiter",
    "get_default_rate_limiter",
    "set_default_rate_limiter",
    "ErrorHandler",
    "ConfigManager",
    "get_default_config_manager",
    "set_default_config_manager",
    # Constants
    "TTS_QUOTA_RPM",
    "TTS_ASSUMED_LATENCY_SEC",
    "TTS_MAX_CONCURRENCY",
    "TTS_MAX_BYTES",
    "TTS_SAFETY_MARGIN",
    "TTS_SAMPLE_RATE",
    "TTS_BATCH_SIZE",
    "DEFAULT_NARRATIVE_MODE",
]
