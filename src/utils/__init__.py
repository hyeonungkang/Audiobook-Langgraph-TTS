"""
Utility modules for TTS Audiobook Converter
"""
# utils.py의 함수들을 re-export (하위 호환성)
# 순환 import를 피하기 위해 여기서는 utils.py를 직접 import하지 않고
# 필요한 함수들은 utils.py에서 직접 import하도록 함
# 대신 logging과 timing 모듈만 여기서 export

from .logging import log_error, print_error, print_warning
from .timing import (
    log_workflow_step_start,
    log_workflow_step_end,
    save_workflow_timing_log,
    get_workflow_timing_summary,
)

# NARRATIVE_MODES는 utils.py에 정의되어 있으므로, 상위 레벨에서 직접 import
# 여기서는 re-export하지 않음 (순환 import 방지)
# 대신 src/cli/interactive.py에서 직접 import하도록 함

__all__ = [
    "log_error",
    "print_error",
    "print_warning",
    "log_workflow_step_start",
    "log_workflow_step_end",
    "save_workflow_timing_log",
    "get_workflow_timing_summary",
]

# utils.py의 함수들을 import하려면 상위 레벨에서 직접 import해야 함
# 예: from ..utils import enforce_segment_count (이것은 src/utils.py를 가리킴)
