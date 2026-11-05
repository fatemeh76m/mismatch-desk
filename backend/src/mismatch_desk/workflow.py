from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .models import Discrepancy, ReconciliationRequest
from .reconciliation import reconcile


class ReconciliationState(TypedDict):
    request: ReconciliationRequest
    discrepancies: list[Discrepancy]
    status: str


def _check_documents(state: ReconciliationState) -> dict[str, object]:
    request = state["request"]
    discrepancies = reconcile(request)
    return {
        "discrepancies": discrepancies,
        "status": "needs_review" if discrepancies else "ready_for_review",
    }


def build_reconciliation_graph():
    """Compile the first workflow slice; review pause/resume comes with persistence."""
    graph = StateGraph(ReconciliationState)
    graph.add_node("check_documents", _check_documents)
    graph.add_edge(START, "check_documents")
    graph.add_edge("check_documents", END)
    return graph.compile()


reconciliation_graph = build_reconciliation_graph()
