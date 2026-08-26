# src/services/assistant_service.py

from typing import Dict, Any

from src.services.ticket_service import process_new_ticket
from src.ml.classification_service import (
    predict_module,
    predict_severity,
)


# ============================================================
# Confidence thresholds
# ============================================================

MODULE_CONFIDENCE_THRESHOLD = 0.60
SEVERITY_CONFIDENCE_THRESHOLD = 0.60


# ============================================================
# Routing decision
# ============================================================

def build_routing_decision(
    duplicate_result: Dict[str, Any],
    module_result: Dict[str, Any],
    severity_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Combine duplicate detection, module prediction,
    severity prediction and confidence checks into one
    final routing recommendation.
    """

    duplicate_decision = duplicate_result["decision"]

    predicted_module = module_result["predicted_module"]
    module_confidence = module_result["confidence"]

    predicted_severity = severity_result["predicted_severity"]
    severity_confidence = severity_result["confidence"]

    review_reasons = []

    # --------------------------------------------------------
    # Classification confidence
    # --------------------------------------------------------

    if module_confidence < MODULE_CONFIDENCE_THRESHOLD:
        review_reasons.append("low_confidence_module")

    if severity_confidence < SEVERITY_CONFIDENCE_THRESHOLD:
        review_reasons.append("low_confidence_severity")

    # --------------------------------------------------------
    # Duplicate handling
    # --------------------------------------------------------

    if duplicate_decision == "auto_duplicate":

        return {
            "routing_status": "closed_as_duplicate",
            "route_to": "duplicate_handling",
            "requires_human_review": False,
            "review_reasons": review_reasons,
            "recommendation": (
                "The ticket is highly similar to an existing ticket "
                "and should be treated as a duplicate."
            ),
        }

    if duplicate_decision == "human_review":

        review_reasons.append("possible_duplicate")

        return {
            "routing_status": "pending_review",
            "route_to": "duplicate_review_queue",
            "requires_human_review": True,
            "review_reasons": review_reasons,
            "recommendation": (
                "Route the ticket to the duplicate review queue "
                f"and associate it with the {predicted_module} module."
            ),
        }

    # --------------------------------------------------------
    # Classification uncertainty
    # --------------------------------------------------------

    if review_reasons:

        return {
            "routing_status": "pending_review",
            "route_to": "classification_review_queue",
            "requires_human_review": True,
            "review_reasons": review_reasons,
            "recommendation": (
                "No strong duplicate was found, but classification "
                "confidence is low. Send the ticket for classification "
                "review before normal routing."
            ),
        }

    # --------------------------------------------------------
    # Normal new ticket
    # --------------------------------------------------------

    return {
        "routing_status": "open",
        "route_to": predicted_module,
        "requires_human_review": False,
        "review_reasons": [],
        "recommendation": (
            f"Route the ticket to the {predicted_module} module "
            f"with severity {predicted_severity}."
        ),
    }


# ============================================================
# Explanation
# ============================================================

def build_explanation(
    duplicate_result: Dict[str, Any],
    module_result: Dict[str, Any],
    severity_result: Dict[str, Any],
    routing_result: Dict[str, Any],
) -> str:
    """
    Produce a concise human-readable explanation
    of the agent's multi-step decision.
    """

    duplicate_decision = duplicate_result["decision"]
    similarity_score = duplicate_result.get("similarity_score")

    predicted_module = module_result["predicted_module"]
    module_confidence = module_result["confidence"]

    predicted_severity = severity_result["predicted_severity"]
    severity_confidence = severity_result["confidence"]

    parts = []

    # Duplicate explanation
    if similarity_score is not None:
        parts.append(
            f"Duplicate analysis returned '{duplicate_decision}' "
            f"with similarity score {similarity_score:.3f}."
        )
    else:
        parts.append(
            f"Duplicate analysis returned '{duplicate_decision}'."
        )

    # Module explanation
    parts.append(
        f"The predicted module is '{predicted_module}' "
        f"with confidence {module_confidence:.3f}."
    )

    # Severity explanation
    parts.append(
        f"The predicted severity is '{predicted_severity}' "
        f"with confidence {severity_confidence:.3f}."
    )

    # Final routing
    parts.append(
        routing_result["recommendation"]
    )

    return " ".join(parts)


# ============================================================
# Main agentic workflow
# ============================================================

def process_ticket_agentically(
    title: str,
    description: str,
) -> Dict[str, Any]:
    """
    Agentic workflow.

    One user request triggers multiple steps automatically:

        1. Duplicate detection
        2. Module prediction
        3. Severity prediction
        4. Confidence evaluation
        5. Routing decision
        6. Explanation

    This version is intentionally read-only:
    it DOES NOT create/update/close tickets in PostgreSQL.
    """

    title = title.strip()
    description = description.strip()

    if not title:
        raise ValueError("Title cannot be empty.")

    if not description:
        raise ValueError("Description cannot be empty.")

    # --------------------------------------------------------
    # Step 1: Duplicate detection
    # --------------------------------------------------------

    duplicate_result = process_new_ticket(
        title=title,
        description=description,
    )

    # --------------------------------------------------------
    # Step 2: Module classification
    # --------------------------------------------------------

    module_result = predict_module(
        title,
        description,
    )

    # --------------------------------------------------------
    # Step 3: Severity classification
    # --------------------------------------------------------

    severity_result = predict_severity(
        title,
        description,
    )

    # --------------------------------------------------------
    # Step 4 + 5: Confidence + routing
    # --------------------------------------------------------

    routing_result = build_routing_decision(
        duplicate_result=duplicate_result,
        module_result=module_result,
        severity_result=severity_result,
    )

    # --------------------------------------------------------
    # Step 6: Explanation
    # --------------------------------------------------------

    explanation = build_explanation(
        duplicate_result=duplicate_result,
        module_result=module_result,
        severity_result=severity_result,
        routing_result=routing_result,
    )

    # --------------------------------------------------------
    # Final structured response
    # --------------------------------------------------------

    return {
        "input": {
            "title": title,
            "description": description,
        },

        "duplicate_analysis": {
            "decision": duplicate_result["decision"],
            "similarity_score": duplicate_result.get(
                "similarity_score"
            ),
            "matched_ticket": duplicate_result.get(
                "matched_ticket"
            ),
        },

        "classification": {
            "module": {
                "predicted_module": module_result[
                    "predicted_module"
                ],
                "confidence": module_result["confidence"],
            },

            "severity": {
                "predicted_severity": severity_result[
                    "predicted_severity"
                ],
                "confidence": severity_result["confidence"],
            },
        },

        "routing": routing_result,

        "explanation": explanation,
    }