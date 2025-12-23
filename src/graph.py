"""
LangGraph StateGraph assembly for TTS Audiobook Converter
"""
from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes.showrunner import showrunner_node
from .nodes.writer import writer_map_node, writer_reduce_node
from .nodes.tts import tts_generator_node
from .nodes.audio_postprocess import audio_postprocess_node


def should_continue_to_writer(state: AgentState) -> str:
    """
    Showrunner 완료 후 segments가 있는지 확인하는 조건부 엣지
    """
    segments = state.get("segments", [])
    if segments and len(segments) > 0:
        return "writer_map"
    else:
        return "error_handler"


def should_continue_to_tts(state: AgentState) -> str:
    """
    Writer 완료 후 scripts가 있는지 확인하는 조건부 엣지
    최소한 하나의 성공한 script가 있으면 TTS로 진행
    """
    scripts = state.get("scripts", [])
    if not scripts:
        return "error_handler"
    
    # 에러가 아닌 실제 스크립트가 있는지 확인
    valid_scripts = [s for s in scripts if s.get("script", "").strip() and not s.get("script", "").strip().startswith("[ERROR:")]
    if valid_scripts and len(valid_scripts) > 0:
        return "tts_generator"
    else:
        return "error_handler"


def error_handler_node(state: AgentState) -> AgentState:
    """
    에러 처리 노드: segments가 없거나 에러가 발생한 경우
    """
    errors = state.get("errors", [])
    if not errors:
        # segments가 없는 경우
        error_info = {
            "node_name": "showrunner",
            "error_message": "No segments generated",
            "segment_id": None
        }
        state["errors"].append(error_info)
    
    print("  ✗ Error: Cannot proceed without segments", flush=True)
    return state


def create_tts_graph() -> StateGraph:
    """
    TTS 오디오북 변환을 위한 LangGraph StateGraph 생성
    
    Returns:
        컴파일된 StateGraph
    """
    # StateGraph 생성
    workflow = StateGraph(AgentState)
    
    # 노드 추가
    workflow.add_node("showrunner", showrunner_node)
    workflow.add_node("writer_map", writer_map_node)
    workflow.add_node("writer_reduce", writer_reduce_node)
    workflow.add_node("tts_generator", tts_generator_node)
    workflow.add_node("audio_postprocess", audio_postprocess_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # 엣지 연결
    # 시작: showrunner
    workflow.set_entry_point("showrunner")
    
    # showrunner → writer_map (조건부) 또는 error_handler
    workflow.add_conditional_edges(
        "showrunner",
        should_continue_to_writer,
        {
            "writer_map": "writer_map",
            "error_handler": "error_handler"
        }
    )
    
    # writer_map → writer_reduce
    # writer_map에서 모든 세그먼트를 병렬 처리하고 결과를 State에 저장
    # writer_reduce는 호환성을 위해 유지 (실제로는 아무 작업도 하지 않음)
    workflow.add_edge("writer_map", "writer_reduce")
    
    # writer_reduce → tts_generator (조건부) 또는 error_handler
    # 최소한 하나의 성공한 script가 있어야 TTS로 진행
    workflow.add_conditional_edges(
        "writer_reduce",
        should_continue_to_tts,
        {
            "tts_generator": "tts_generator",
            "error_handler": "error_handler"
        }
    )
    
    # tts_generator → audio_postprocess
    workflow.add_edge("tts_generator", "audio_postprocess")
    
    # audio_postprocess → END
    workflow.add_edge("audio_postprocess", END)
    
    # error_handler → END
    workflow.add_edge("error_handler", END)
    
    # 그래프 컴파일
    app = workflow.compile()
    
    return app


def compile_graph() -> StateGraph:
    """
    그래프를 컴파일하여 반환
    
    Returns:
        컴파일된 StateGraph 앱
    """
    return create_tts_graph()

