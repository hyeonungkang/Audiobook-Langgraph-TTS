"""
Narrative mode definitions and metadata
서사 모드 관련 메타데이터 정의
"""
from ..core.constants import DEFAULT_NARRATIVE_MODE

# 순환 import를 피하기 위해, NARRATIVE_MODES는 utils.py에 정의되어 있음
# lazy import로 처리
_NARRATIVE_MODES_CACHE = None

def _load_narrative_modes():
    """NARRATIVE_MODES를 lazy load"""
    global _NARRATIVE_MODES_CACHE
    if _NARRATIVE_MODES_CACHE is None:
        # utils.py에서 직접 import 시도
        try:
            # 상대 import로 접근
            from .. import utils as utils_module
            # utils.py는 utils 패키지가 아니라 상위 레벨에 있음
            # 따라서 직접 접근 불가
            # 대신: utils.py를 실행하여 NARRATIVE_MODES만 추출
            import sys
            import importlib.util
            from pathlib import Path
            
            utils_py_path = Path(__file__).parent.parent / "utils.py"
            if utils_py_path.exists():
                # utils.py를 모듈로 로드
                spec = importlib.util.spec_from_file_location("_temp_utils", utils_py_path)
                temp_utils = importlib.util.module_from_spec(spec)
                # 필요한 의존성 모듈들을 sys.modules에 등록
                if "src" not in sys.modules:
                    import types
                    sys.modules["src"] = types.ModuleType("src")
                # config 모듈 등록
                if "src.config" not in sys.modules:
                    from .. import config
                    sys.modules["src.config"] = config
                # core 모듈 등록
                if "src.core" not in sys.modules:
                    from .. import core
                    sys.modules["src.core"] = core
                # models 모듈 등록
                if "src.models" not in sys.modules:
                    from .. import models
                    sys.modules["src.models"] = models
                # utils.logging 등록
                if "src.utils" not in sys.modules:
                    import types
                    sys.modules["src.utils"] = types.ModuleType("src.utils")
                if "src.utils.logging" not in sys.modules:
                    from ..utils import logging
                    sys.modules["src.utils.logging"] = logging
                if "src.utils.timing" not in sys.modules:
                    from ..utils import timing
                    sys.modules["src.utils.timing"] = timing
                
                spec.loader.exec_module(temp_utils)
                _NARRATIVE_MODES_CACHE = temp_utils.NARRATIVE_MODES
            else:
                _NARRATIVE_MODES_CACHE = {}
        except Exception as e:
            # Fallback: 빈 딕셔너리
            _NARRATIVE_MODES_CACHE = {}
    return _NARRATIVE_MODES_CACHE

# NARRATIVE_MODES를 property처럼 동작하도록 함
class _NarrativeModesProxy:
    """NARRATIVE_MODES를 lazy load하는 프록시"""
    def keys(self):
        return _load_narrative_modes().keys()
    
    def get(self, key, default=None):
        return _load_narrative_modes().get(key, default)
    
    def __getitem__(self, key):
        return _load_narrative_modes()[key]
    
    def __contains__(self, key):
        return key in _load_narrative_modes()
    
    def __iter__(self):
        return iter(_load_narrative_modes())
    
    def __len__(self):
        return len(_load_narrative_modes())

NARRATIVE_MODES = _NarrativeModesProxy()

__all__ = ["NARRATIVE_MODES", "DEFAULT_NARRATIVE_MODE"]
