"""
Workflow timing utilities for TTS Audiobook Converter
"""
import time
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..config import application_path
from .logging import log_error


# 워크플로우 타이밍 로깅을 위한 전역 변수
_workflow_timing_data: dict = {}
_workflow_timing_lock = threading.Lock()


def log_workflow_step_start(step_name: str) -> float:
    """
    워크플로우 스텝 시작 시간을 기록합니다.
    
    Args:
        step_name: 스텝 이름 (예: "showrunner", "writer_map", "tts_generator", "audio_postprocess")
    
    Returns:
        시작 시간 (timestamp)
    """
    start_time = time.time()
    with _workflow_timing_lock:
        if step_name not in _workflow_timing_data:
            _workflow_timing_data[step_name] = []
        _workflow_timing_data[step_name].append({
            "start_time": start_time,
            "start_time_str": datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "end_time": None,
            "end_time_str": None,
            "duration_seconds": None
        })
    return start_time


def log_workflow_step_end(step_name: str, start_time: Optional[float] = None) -> float:
    """
    워크플로우 스텝 완료 시간을 기록합니다.
    
    Args:
        step_name: 스텝 이름
        start_time: 시작 시간 (None이면 가장 최근 시작 시간 사용)
    
    Returns:
        소요 시간 (초)
    """
    end_time = time.time()
    with _workflow_timing_lock:
        if step_name not in _workflow_timing_data:
            return 0.0
        
        # 가장 최근에 시작된 항목 찾기
        entries = _workflow_timing_data[step_name]
        if not entries:
            return 0.0
        
        # end_time이 None인 가장 최근 항목 찾기
        for entry in reversed(entries):
            if entry["end_time"] is None:
                if start_time is None or abs(entry["start_time"] - start_time) < 0.1:
                    entry["end_time"] = end_time
                    entry["end_time_str"] = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    entry["duration_seconds"] = end_time - entry["start_time"]
                    return entry["duration_seconds"]
    
    return 0.0


def save_workflow_timing_log() -> Optional[Path]:
    """
    워크플로우 타이밍 데이터를 JSON 파일로 저장합니다.
    
    Returns:
        저장된 파일 경로 (실패 시 None)
    """
    try:
        logs_dir = application_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"workflow_timing_{timestamp}.json"
        
        with _workflow_timing_lock:
            # 통계 계산
            stats = {}
            for step_name, entries in _workflow_timing_data.items():
                completed = [e for e in entries if e["duration_seconds"] is not None]
                if completed:
                    durations = [e["duration_seconds"] for e in completed]
                    stats[step_name] = {
                        "count": len(completed),
                        "total_seconds": sum(durations),
                        "avg_seconds": sum(durations) / len(durations),
                        "min_seconds": min(durations),
                        "max_seconds": max(durations)
                    }
            
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "steps": _workflow_timing_data.copy(),
                "statistics": stats
            }
            
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return log_file
    except Exception as e:
        log_error(f"Failed to save workflow timing log: {e}", context="save_workflow_timing_log", exception=e)
        return None


def get_workflow_timing_summary() -> dict:
    """
    현재 워크플로우 타이밍 요약 정보를 반환합니다.
    
    Returns:
        타이밍 요약 딕셔너리
    """
    with _workflow_timing_lock:
        summary = {}
        for step_name, entries in _workflow_timing_data.items():
            completed = [e for e in entries if e["duration_seconds"] is not None]
            if completed:
                latest = completed[-1]
                summary[step_name] = {
                    "duration_seconds": latest["duration_seconds"],
                    "start_time_str": latest["start_time_str"],
                    "end_time_str": latest["end_time_str"]
                }
        return summary
