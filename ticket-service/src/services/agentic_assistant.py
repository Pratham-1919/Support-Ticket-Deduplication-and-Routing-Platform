
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from src.services.ticket_service import process_new_ticket
from src.ml.classification_service import predict_module, predict_severity

MODULE_CONFIDENCE_THRESHOLD = 0.60
SEVERITY_CONFIDENCE_THRESHOLD = 0.60


class TicketAgentState(TypedDict):
    title: str
    description: str
    dedup_result: Optional[dict]
    module_prediction: Optional[dict]
    severity_prediction: Optional[dict]
    routing_decision: Optional[str]
    explanation: Optional[str]


def dedup_node(state: TicketAgentState) -> TicketAgentState:
    state["dedup_result"] = process_new_ticket(state["title"], state["description"])
    return state


def classify_module_node(state: TicketAgentState) -> TicketAgentState:
    state["module_prediction"] = predict_module(state["title"], state["description"])
    return state


def classify_severity_node(state: TicketAgentState) -> TicketAgentState:
    state["severity_prediction"] = predict_severity(state["title"], state["description"])
    return state


def decide_routing_node(state: TicketAgentState) -> TicketAgentState:
    dedup = state["dedup_result"]

    if dedup["decision"] == "auto_duplicate":
        decision = "close_as_duplicate"
        explanation = dedup["message"]
    elif dedup["decision"] == "human_review":
        decision = "hold_for_review"
        explanation = dedup["message"]
    else:
        mod = state["module_prediction"]
        sev = state["severity_prediction"]
        if mod["confidence"] < MODULE_CONFIDENCE_THRESHOLD or sev["confidence"] < SEVERITY_CONFIDENCE_THRESHOLD:
            decision = "hold_for_review"
        else:
            decision = "route_to_module"
        explanation = (
            f"{dedup['message']} Predicted module: {mod['predicted_module']} "
            f"(confidence {mod['confidence']:.2f}). Predicted severity: "
            f"{sev['predicted_severity']} (confidence {sev['confidence']:.2f})."
        )

    state["routing_decision"] = decision
    state["explanation"] = explanation
    return state


def should_classify(state: TicketAgentState) -> str:
    """Conditional branch: skip classification entirely if it's already an auto-duplicate."""
    if state["dedup_result"]["decision"] == "auto_duplicate":
        return "decide_routing"
    return "classify_module"


# ---- Build the graph ----
graph = StateGraph(TicketAgentState)
graph.add_node("dedup_check", dedup_node)
graph.add_node("classify_module", classify_module_node)
graph.add_node("classify_severity", classify_severity_node)
graph.add_node("decide_routing", decide_routing_node)

graph.set_entry_point("dedup_check")
graph.add_conditional_edges(
    "dedup_check", should_classify,
    {"classify_module": "classify_module", "decide_routing": "decide_routing"},
)
graph.add_edge("classify_module", "classify_severity")
graph.add_edge("classify_severity", "decide_routing")
graph.add_edge("decide_routing", END)

compiled_graph = graph.compile()


def process_ticket_agentically(title: str, description: str) -> dict:
    initial_state: TicketAgentState = {
        "title": title, "description": description,
        "dedup_result": None, "module_prediction": None,
        "severity_prediction": None, "routing_decision": None, "explanation": None,
    }
    final_state = compiled_graph.invoke(initial_state)
    return {
        "steps": {
            "1_duplicate_check": final_state["dedup_result"],
            "2_module_prediction": final_state["module_prediction"],
            "3_severity_prediction": final_state["severity_prediction"],
        },
        "routing_decision": final_state["routing_decision"],
        "explanation": final_state["explanation"],
    }