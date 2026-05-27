from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from models.state import HRWorkflowState
from graph.nodes import (
    parse_uploads_node,
    shortlist_resumes_node,
    hitl_shortlist_node,
    pre_screening_node,
    hitl_pre_screening_node,
    email_interview_scheduler_node,
    hitl_onboarding_node,
    onboarding_node,
)
from graph.edges import (
    route_after_shortlist_hitl,
    route_after_pre_screening_hitl,
    route_after_onboarding_hitl,
)
from core.logging import get_logger

logger = get_logger("graph.workflow")

_graph = None
_checkpointer = None


def build_graph():
    """Build and compile the LangGraph HR workflow."""
    global _graph, _checkpointer

    checkpointer = MemorySaver()

    builder = StateGraph(HRWorkflowState)

    # Register nodes
    builder.add_node("parse_uploads", parse_uploads_node)
    builder.add_node("shortlist_resumes", shortlist_resumes_node)
    builder.add_node("hitl_shortlist", hitl_shortlist_node)
    builder.add_node("pre_screening", pre_screening_node)
    builder.add_node("hitl_pre_screening", hitl_pre_screening_node)
    builder.add_node("email_interview_scheduler", email_interview_scheduler_node)
    builder.add_node("hitl_onboarding", hitl_onboarding_node)
    builder.add_node("onboarding", onboarding_node)

    # Edges
    builder.add_edge(START, "parse_uploads")
    builder.add_edge("parse_uploads", "shortlist_resumes")
    builder.add_edge("shortlist_resumes", "hitl_shortlist")

    builder.add_conditional_edges(
        "hitl_shortlist",
        route_after_shortlist_hitl,
        {
            "pre_screening": "pre_screening",
            "shortlist_resumes": "shortlist_resumes",
            "hitl_shortlist": "hitl_shortlist",
        },
    )

    builder.add_edge("pre_screening", "hitl_pre_screening")

    builder.add_conditional_edges(
        "hitl_pre_screening",
        route_after_pre_screening_hitl,
        {
            "email_interview_scheduler": "email_interview_scheduler",
            "pre_screening": "pre_screening",
            "hitl_pre_screening": "hitl_pre_screening",
        },
    )

    builder.add_edge("email_interview_scheduler", "hitl_onboarding")

    builder.add_conditional_edges(
        "hitl_onboarding",
        route_after_onboarding_hitl,
        {
            "onboarding": "onboarding",
            "hitl_onboarding": "hitl_onboarding",
        },
    )

    builder.add_edge("onboarding", END)

    # interrupt_before pauses execution before these nodes, allowing HITL
    _graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_shortlist", "hitl_pre_screening", "hitl_onboarding"],
    )
    _checkpointer = checkpointer
    logger.info("graph_compiled")
    return _graph


def get_graph():
    global _graph
    if _graph is None:
        build_graph()
    return _graph


def get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        build_graph()
    return _checkpointer


def make_config(thread_id: str) -> dict:
    """LangGraph config dict for a given thread."""
    return {"configurable": {"thread_id": thread_id}}
