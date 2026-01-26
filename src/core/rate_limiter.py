"""
Rate Limiter for TTS API requests
전역 변수를 클래스로 캡슐화하여 테스트 가능하고 재사용 가능한 구조로 개선
"""
import time
from collections import deque
from threading import Lock
from typing import Optional
from .constants import TTS_QUOTA_RPM


class RateLimiter:
    """
    TTS API 요청을 위한 Rate Limiter
    
    분당 쿼터 제한을 관리하고, 요청 전에 자동으로 대기합니다.
    """
    
    def __init__(self, quota_rpm: float = TTS_QUOTA_RPM):
        """
        Args:
            quota_rpm: 분당 요청 한도 (기본값: TTS_QUOTA_RPM)
        """
        self.quota_rpm = quota_rpm
        self._request_times: deque = deque()
        self._lock = Lock()
    
    def wait_if_needed(self) -> None:
        """
        분당 쿼터 제한을 위한 rate limiting. 각 요청 전에 호출해야 함.
        
        이 함수는:
        1. 최근 1분간의 요청 수를 확인
        2. 쿼터에 도달했다면 가장 오래된 요청이 1분 전이 될 때까지 대기
        3. 요청 시간을 기록 (내부에서 자동 기록)
        """
        with self._lock:
            now = time.time()
            # 1분 이전의 기록 제거
            while self._request_times and self._request_times[0] < now - 60:
                self._request_times.popleft()
            
            # 분당 쿼터 제한 확인
            current_count = len(self._request_times)
            # 9개까지는 1분 안에 다 보낼 수 있도록 허용 (9개 초과 시에만 대기)
            if current_count >= int(self.quota_rpm):
                # 가장 오래된 요청이 1분 전이 될 때까지 대기
                oldest_time = self._request_times[0]
                wait_time = oldest_time + 60 - now + 0.5  # 0.5초 안전 마진
                if wait_time > 0:
                    time.sleep(wait_time)
                    # 다시 정리
                    now = time.time()
                    while self._request_times and self._request_times[0] < now - 60:
                        self._request_times.popleft()
            
            # 현재 요청 시간 기록
            self._request_times.append(time.time())
    
    def reset(self) -> None:
        """
        Rate limiter 상태를 초기화합니다.
        Rate limit 에러 후 새로운 윈도우를 시작할 때 사용.
        """
        with self._lock:
            now = time.time()
            # 최근 1분간의 요청 기록을 모두 제거하여 새로운 윈도우 시작
            while self._request_times and self._request_times[0] < now - 60:
                self._request_times.popleft()
    
    def get_current_count(self) -> int:
        """
        현재 1분 윈도우 내의 요청 수를 반환합니다.
        
        Returns:
            현재 요청 수
        """
        with self._lock:
            now = time.time()
            # 1분 이전의 기록 제거
            while self._request_times and self._request_times[0] < now - 60:
                self._request_times.popleft()
            return len(self._request_times)


# 전역 인스턴스 (하위 호환성을 위해)
_default_rate_limiter: Optional[RateLimiter] = None


def get_default_rate_limiter() -> RateLimiter:
    """
    전역 RateLimiter 인스턴스를 반환합니다.
    
    Returns:
        전역 RateLimiter 인스턴스
    """
    global _default_rate_limiter
    if _default_rate_limiter is None:
        _default_rate_limiter = RateLimiter()
    return _default_rate_limiter


def set_default_rate_limiter(limiter: RateLimiter) -> None:
    """
    전역 RateLimiter 인스턴스를 설정합니다.
    
    Args:
        limiter: RateLimiter 인스턴스
    """
    global _default_rate_limiter
    _default_rate_limiter = limiter
