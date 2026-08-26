import uuid
from typing import Optional
from sqlalchemy.orm import Session
from src.core.logging_config import logger

from src.db.models import Module, Ticket, DuplicateLink
from src.ml.similarity_search import search_similar_tickets
from src.ml.classification_service import predict_module, predict_severity

AUTO_DUPLICATE_THRESHOLD = 0.85
HUMAN_REVIEW_THRESHOLD = 0.65
MODULE_CONFIDENCE_THRESHOLD = 0.60
SEVERITY_CONFIDENCE_THRESHOLD = 0.60


def build_matched_ticket(best_match):
    postgres_data = best_match.get("postgres") or {}
    return {
        "ticket_id": best_match["ticket_id"],
        "similarity_score": best_match["similarity_score"],
        "title": postgres_data.get("title"),
        "description": postgres_data.get("description"),
    }


def process_new_ticket(title: str, description: str,
                        module: Optional[str] = None,
                        component: Optional[str] = None):
    # NOTE: unchanged -- this talks to ChromaDB + does its own Postgres
    # enrichment inside search_similar_tickets, which we're leaving as-is.
    results = search_similar_tickets(title=title, description=description, top_k=5)

    if not results:
        return {"decision": "new_ticket", "message": "No similar ticket was found.",
                "similarity_score": None, "matched_ticket": None}

    best_match = results[0]
    similarity_score = best_match["similarity_score"]
    matched_ticket = build_matched_ticket(best_match)

    if similarity_score >= AUTO_DUPLICATE_THRESHOLD:
        return {"decision": "auto_duplicate",
                "message": "A highly similar ticket was found. The ticket should be treated as a duplicate.",
                "similarity_score": similarity_score, "matched_ticket": matched_ticket}

    if similarity_score >= HUMAN_REVIEW_THRESHOLD:
        return {"decision": "human_review",
                "message": "A potentially similar ticket was found. Human review is required.",
                "similarity_score": similarity_score, "matched_ticket": matched_ticket}

    return {"decision": "new_ticket",
            "message": "No sufficiently similar ticket was found. This appears to be a new ticket.",
            "similarity_score": similarity_score, "matched_ticket": matched_ticket}


def create_ticket(db: Session, title, description, module=None, component=None,
                   severity=None, priority=None, ticket_type="bug_report"):
    needs_review_reasons = []

    if module is None:
        pred = predict_module(title, description)
        module = pred["predicted_module"]
        if pred["confidence"] < MODULE_CONFIDENCE_THRESHOLD:
            needs_review_reasons.append("low_confidence_module")

    if severity is None and ticket_type == "bug_report":
        pred = predict_severity(title, description)
        severity = pred["predicted_severity"]
        if pred["confidence"] < SEVERITY_CONFIDENCE_THRESHOLD:
            needs_review_reasons.append("low_confidence_severity")

    module_obj = db.query(Module).filter(Module.name.ilike(module)).first()
    if module_obj is None:
        raise ValueError(f"Unknown module: {module}")

    if ticket_type == "feature_request":
        decision_info = {"decision": "new_ticket",
                          "message": "Feature requests skip duplicate detection and are routed directly.",
                          "similarity_score": None, "matched_ticket": None}
        ticket_status = "open"
    else:
        decision_info = process_new_ticket(title, description, module=module, component=component)
        ticket_status = {"auto_duplicate": "closed_as_duplicate",
                          "human_review": "pending_review",
                          "new_ticket": "open"}[decision_info["decision"]]

    if needs_review_reasons and ticket_status == "open":
        ticket_status = "pending_review"

    review_reasons_str = ",".join(needs_review_reasons) if needs_review_reasons else None

    new_ticket = Ticket(
        external_id=f"local-{uuid.uuid4()}",
        module_id=module_obj.id,
        ticket_type=ticket_type,
        title=title,
        description=description,
        component=component,
        severity=severity,
        priority=priority,
        status=ticket_status,
        is_open=(ticket_status != "closed_as_duplicate"),
        is_confirmed=False,
        review_reasons=review_reasons_str,
    )
    db.add(new_ticket)
    db.flush()

    duplicate_link_id = None
    matched = decision_info.get("matched_ticket")
    if matched and decision_info["decision"] in ("auto_duplicate", "human_review"):
        matched_id = str(matched["ticket_id"])
        orig = db.query(Ticket).filter(
            (Ticket.external_id == matched_id) |
            (Ticket.id == int(matched_id) if matched_id.isdigit() else False)
        ).first()
        if orig:
            link_status = "confirmed" if decision_info["decision"] == "auto_duplicate" else "pending_review"
            link = DuplicateLink(
                ticket_id=new_ticket.id,
                duplicate_of_ticket_id=orig.id,
                source="model_detected",
                similarity_score=matched["similarity_score"],
                status=link_status,
            )
            db.add(link)
            db.flush()
            duplicate_link_id = link.id

    db.commit()
    db.refresh(new_ticket)
    logger.info(
        f"Ticket {new_ticket.id} created: decision={decision_info['decision']}, "
        f"status={ticket_status}, module={module}, severity={severity}"
    )
    

    return {"ticket_id": new_ticket.id, "status": ticket_status, "module": module,
            "severity": severity, "needs_review_reasons": needs_review_reasons,
            "duplicate_link_id": duplicate_link_id, **decision_info}