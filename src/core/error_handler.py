"""
Error Handler for standardized error handling across nodes
"""
from typing import Optional, Dict, Any
from ..utils.logging import log_error, print_error, print_warning


class ErrorHandler:
    """
    공통 에러 처리 로직을 통합한 클래스
    노드별 에러 포맷팅을 표준화
    """
    
    @staticmethod
    def handle_node_error(
        node_name: str,
        error: Exception,
        segment_id: Optional[int] = None,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        노드에서 발생한 에러를 표준 형식으로 처리합니다.
        
        Args:
            node_name: 노드 이름 (예: "showrunner", "writer_map", "tts_generator")
            error: 발생한 예외
            segment_id: 세그먼트 ID (해당되는 경우)
            context: 추가 컨텍스트 정보
        
        Returns:
            표준화된 에러 정보 딕셔너리
        """
        error_info = {
            "node_name": node_name,
            "error_message": str(error),
            "error_type": type(error).__name__,
            "segment_id": segment_id,
        }
        
        if context:
            error_info["context"] = context
        
        # 로깅
        log_error(
            f"{node_name} error" + (f" (segment {segment_id})" if segment_id else ""),
            context=context or node_name,
            exception=error
        )
        
        # 콘솔 출력
        print_error(
            f"{node_name} failed: {str(error)}",
            context=context or node_name,
            exception=error
        )
        
        return error_info
    
    @staticmethod
    def handle_warning(
        node_name: str,
        message: str,
        segment_id: Optional[int] = None,
        context: Optional[str] = None
    ) -> None:
        """
        경고 메시지를 표준 형식으로 처리합니다.
        
        Args:
            node_name: 노드 이름
            message: 경고 메시지
            segment_id: 세그먼트 ID (해당되는 경우)
            context: 추가 컨텍스트 정보
        """
        full_message = message
        if segment_id:
            full_message = f"Segment {segment_id}: {message}"
        
        print_warning(full_message, context=context or node_name)
