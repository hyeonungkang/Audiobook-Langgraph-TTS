"""
Config Manager for unified configuration management
config.py와 config_builder.py의 기능을 통합
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import google.generativeai as genai

from ..config import (
    application_path,
    CONFIG_PATH,
    OUTPUT_ROOT,
    ADDITIONAL_OUTPUT_ROOT,
    LATEST_RUN_MARKER,
    load_config as _load_config,
    save_config as _save_config,
    initialize_api_keys as _setup_gemini,  # setup_gemini는 initialize_api_keys의 별칭
)
from ..config_builder import build_config as _build_config


class ConfigManager:
    """
    설정 관리를 통합한 클래스
    config.py와 config_builder.py의 기능을 클래스로 캡슐화
    """
    
    def __init__(self):
        """ConfigManager 초기화"""
        self._config: Optional[Dict[str, Any]] = None
        self._application_path = application_path
        self._config_path = CONFIG_PATH
        self._output_root = OUTPUT_ROOT
        self._additional_output_root = ADDITIONAL_OUTPUT_ROOT
        self._latest_run_marker = LATEST_RUN_MARKER
    
    @property
    def application_path(self) -> Path:
        """애플리케이션 경로"""
        return self._application_path
    
    @property
    def config_path(self) -> Path:
        """설정 파일 경로"""
        return self._config_path
    
    @property
    def output_root(self) -> Path:
        """출력 루트 디렉토리"""
        return self._output_root
    
    @property
    def additional_output_root(self) -> Path:
        """추가 출력 루트 디렉토리"""
        return self._additional_output_root
    
    @property
    def latest_run_marker(self) -> Path:
        """최근 실행 경로 마커 파일"""
        return self._latest_run_marker
    
    def load(self) -> Dict[str, Any]:
        """
        설정을 로드합니다.
        
        Returns:
            설정 딕셔너리
        """
        if self._config is None:
            self._config = _load_config()
        return self._config.copy()
    
    def save(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        설정을 저장합니다.
        
        Args:
            config: 저장할 설정 (None이면 현재 설정 저장)
        """
        if config is not None:
            self._config = config
        if self._config is not None:
            _save_config(self._config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        설정 값을 가져옵니다.
        
        Args:
            key: 설정 키
            default: 기본값
        
        Returns:
            설정 값
        """
        if self._config is None:
            self.load()
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        설정 값을 설정합니다.
        
        Args:
            key: 설정 키
            value: 설정 값
        """
        if self._config is None:
            self.load()
        self._config[key] = value
    
    def build_from_raw(self, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        프론트엔드에서 받은 단순 설정값을 CLI와 동일한 형태의 풍부한 설정 객체로 변환합니다.
        
        Args:
            raw_config: 프론트엔드에서 전송한 설정 딕셔너리
        
        Returns:
            AgentState에서 사용할 수 있는 완전한 config 객체
        """
        return _build_config(raw_config)
    
    def setup_gemini_api(self) -> None:
        """
        Gemini API를 설정합니다.
        """
        _setup_gemini()


# 전역 인스턴스 (하위 호환성을 위해)
_default_config_manager: Optional[ConfigManager] = None


def get_default_config_manager() -> ConfigManager:
    """
    전역 ConfigManager 인스턴스를 반환합니다.
    
    Returns:
        전역 ConfigManager 인스턴스
    """
    global _default_config_manager
    if _default_config_manager is None:
        _default_config_manager = ConfigManager()
    return _default_config_manager


def set_default_config_manager(manager: ConfigManager) -> None:
    """
    전역 ConfigManager 인스턴스를 설정합니다.
    
    Args:
        manager: ConfigManager 인스턴스
    """
    global _default_config_manager
    _default_config_manager = manager
