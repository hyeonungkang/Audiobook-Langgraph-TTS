"""
Logging utilities for TTS Audiobook Converter
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..config import application_path


def log_error(message: str, context: str = "general", exception: Optional[Exception] = None) -> None:
    """
    Append error messages to a log file with timestamps for troubleshooting.
    
    Args:
        message: Error message to log
        context: Context where the error occurred
        exception: Optional exception object
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_path = application_path / "error_log.txt"
        with open(log_path, "a", encoding="utf-8") as f:
            error_msg = f"[{timestamp}] ({context}) {message}"
            if exception:
                error_msg += f"\n  Exception type: {type(exception).__name__}"
                error_msg += f"\n  Exception details: {str(exception)}"
                import traceback
                tb_str = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
                error_msg += f"\n  Traceback:\n{tb_str}"
            error_msg += "\n"
            f.write(error_msg)
    except Exception:
        pass


def print_error(message: str, context: str = "general", exception: Optional[Exception] = None) -> None:
    """
    Print error message to console and log it to file.
    
    Args:
        message: Error message to display
        context: Context where the error occurred
        exception: Optional exception object
    """
    error_prefix = f"✗ [{context}] {message}"
    print(error_prefix, flush=True)
    
    if exception:
        print(f"  Exception type: {type(exception).__name__}", flush=True)
        print(f"  Exception details: {str(exception)}", flush=True)
    
    # Also log to file
    log_error(message, context, exception)


def print_warning(message: str, context: str = "general", exception: Optional[Exception] = None) -> None:
    """
    Print warning message to console and optionally log it.
    
    Args:
        message: Warning message to display
        context: Context where the warning occurred
        exception: Optional exception object
    """
    warning_prefix = f"⚠ [{context}] {message}"
    print(warning_prefix, flush=True)
    
    if exception:
        print(f"  Exception type: {type(exception).__name__}", flush=True)
        print(f"  Exception details: {str(exception)}", flush=True)
