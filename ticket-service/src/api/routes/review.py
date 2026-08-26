import os
import httpx

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, aliased

from src.core.security import require_role
from src.db.session import get_db
from src.db.models import Ticket, Module, DuplicateLink
from src.core.logging_config import logger


router = APIRouter(
    prefix="/review-queue",
    tags=["review"],
)


DOC_SERVICE_URL = os.getenv(
    "DOC_SERVICE_URL",
    "http://localhost:8001",
)


# ============================================================
# 1. LIST PENDING DUPLICATE REVIEWS
# ============================================================

@router.get("/")
def list_pending_reviews(
    db: Session = Depends(get_db),
):
    """
    Return duplicate matches that are waiting for
    support-engineer/admin review.
    """

    TicketDup = aliased(Ticket)
    TicketOrig = aliased(Ticket)

    rows = (
        db.query(
            DuplicateLink.id,
            TicketDup.id,
            TicketDup.title,
            TicketOrig.id,
            TicketOrig.title,
            DuplicateLink.similarity_score,
            DuplicateLink.created_at,
        )
        .join(
            TicketDup,
            TicketDup.id == DuplicateLink.ticket_id,
        )
        .join(
            TicketOrig,
            TicketOrig.id
            == DuplicateLink.duplicate_of_ticket_id,
        )
        .filter(
            DuplicateLink.status == "pending_review"
        )
        .order_by(
            DuplicateLink.created_at
        )
        .all()
    )

    return [
        {
            "duplicate_link_id": row[0],
            "new_ticket_id": row[1],
            "new_ticket_title": row[2],
            "matched_ticket_id": row[3],
            "matched_ticket_title": row[4],
            "similarity_score": row[5],
            "created_at": row[6],
        }
        for row in rows
    ]


# ============================================================
# 2. CONFIRM DUPLICATE
# ============================================================

@router.post("/{duplicate_link_id}/confirm")
def confirm_duplicate(
    duplicate_link_id: int,
    current_user: dict = Depends(
        require_role(
            "admin",
            "support_engineer",
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Confirm that a pending duplicate match is correct.

    Actions:
        1. duplicate_links.status -> confirmed
        2. tickets.status -> closed_as_duplicate
        3. tickets.is_open -> False
        4. trigger document-service ticket summary
    """

    # --------------------------------------------------------
    # Find only a PENDING duplicate link
    # --------------------------------------------------------

    link = (
        db.query(DuplicateLink)
        .filter(
            DuplicateLink.id == duplicate_link_id,
            DuplicateLink.status == "pending_review",
        )
        .first()
    )

    if link is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Duplicate link not found or "
                "has already been reviewed"
            ),
        )

    # --------------------------------------------------------
    # Find the submitted/new ticket
    # --------------------------------------------------------

    ticket_obj = (
        db.query(Ticket)
        .filter(
            Ticket.id == link.ticket_id
        )
        .first()
    )

    if ticket_obj is None:
        raise HTTPException(
            status_code=404,
            detail="ticket not found",
        )

    # --------------------------------------------------------
    # Confirm duplicate
    # --------------------------------------------------------

    link.status = "confirmed"

    ticket_obj.status = "closed_as_duplicate"
    ticket_obj.is_open = False

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    # --------------------------------------------------------
    # Trigger document service
    # --------------------------------------------------------

    summary_generated = False
    summary_error = None

    try:
        response = httpx.post(
            (
                f"{DOC_SERVICE_URL}"
                "/documents/ticket-summary"
            ),
            params={
                "ticket_id": ticket_obj.id
            },
            timeout=10.0,
        )

        response.raise_for_status()

        summary_generated = True

        logger.info(f"Summary generated successfully for ticket {ticket_obj.id}")

    except Exception as error:
        summary_error = str(error)

        logger.warning(f"Failed to generate summary for ticket {ticket_obj.id}: {error}")

    return {
        "duplicate_link_id": duplicate_link_id,
        "ticket_id": ticket_obj.id,
        "status": "confirmed",
        "ticket_status": "closed_as_duplicate",
        "summary_generated": summary_generated,
        "summary_error": summary_error,
    }


# ============================================================
# 3. REJECT DUPLICATE
# ============================================================

@router.post("/{duplicate_link_id}/reject")
def reject_duplicate(
    duplicate_link_id: int,
    current_user: dict = Depends(
        require_role(
            "admin",
            "support_engineer",
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Reject a pending duplicate match.

    Actions:
        1. duplicate_links.status -> rejected
        2. ticket returns to open status
    """

    # --------------------------------------------------------
    # Find only a PENDING duplicate link
    # --------------------------------------------------------

    link = (
        db.query(DuplicateLink)
        .filter(
            DuplicateLink.id == duplicate_link_id,
            DuplicateLink.status == "pending_review",
        )
        .first()
    )

    if link is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Duplicate link not found or "
                "has already been reviewed"
            ),
        )

    # --------------------------------------------------------
    # Find ticket
    # --------------------------------------------------------

    ticket_obj = (
        db.query(Ticket)
        .filter(
            Ticket.id == link.ticket_id
        )
        .first()
    )

    if ticket_obj is None:
        raise HTTPException(
            status_code=404,
            detail="ticket not found",
        )

    # --------------------------------------------------------
    # Reject duplicate
    # --------------------------------------------------------

    link.status = "rejected"

    ticket_obj.status = "open"
    ticket_obj.is_open = True

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "duplicate_link_id": duplicate_link_id,
        "ticket_id": ticket_obj.id,
        "status": "rejected",
        "ticket_status": "open",
    }


# ============================================================
# 4. LIST CLASSIFICATION REVIEWS
# ============================================================

@router.get("/classifications")
def list_classification_reviews(
    db: Session = Depends(get_db),
):
    """
    List tickets waiting for review because the
    module/severity classifier had low confidence.
    """

    rows = (
        db.query(
            Ticket,
            Module.name,
        )
        .join(
            Module,
            Ticket.module_id == Module.id,
        )
        .filter(
            Ticket.status == "pending_review",
            Ticket.review_reasons.isnot(None),
        )
        .order_by(
            Ticket.id
        )
        .all()
    )

    return [
        {
            "ticket_id": ticket_obj.id,
            "title": ticket_obj.title,
            "description": ticket_obj.description,
            "predicted_module": module_name,
            "predicted_severity": (
                ticket_obj.severity
            ),
            "reasons": (
                ticket_obj.review_reasons.split(",")
                if ticket_obj.review_reasons
                else []
            ),
            "ticket_type": ticket_obj.ticket_type,
        }
        for ticket_obj, module_name in rows
    ]


# ============================================================
# 5. CONFIRM CLASSIFICATION
# ============================================================

@router.post(
    "/classifications/{ticket_id}/confirm"
)
def confirm_classification(
    ticket_id: int,
    current_user: dict = Depends(
        require_role(
            "admin",
            "support_engineer",
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Accept the predicted module/severity as-is.
    """

    ticket_obj = (
        db.query(Ticket)
        .filter(
            Ticket.id == ticket_id,
            Ticket.status == "pending_review",
        )
        .first()
    )

    if ticket_obj is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "ticket not found or "
                "not pending review"
            ),
        )

    ticket_obj.status = "open"
    ticket_obj.review_reasons = None
    ticket_obj.is_open = True

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "ticket_id": ticket_id,
        "status": "open",
    }


# ============================================================
# 6. OVERRIDE CLASSIFICATION
# ============================================================

@router.post(
    "/classifications/{ticket_id}/override"
)
def override_classification(
    ticket_id: int,
    module: str = None,
    severity: str = None,
    current_user: dict = Depends(
        require_role(
            "admin",
            "support_engineer",
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Correct the module and/or severity prediction.
    """

    if not module and not severity:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide module and/or severity "
                "to override"
            ),
        )

    ticket_obj = (
        db.query(Ticket)
        .filter(
            Ticket.id == ticket_id
        )
        .first()
    )

    if ticket_obj is None:
        raise HTTPException(
            status_code=404,
            detail="ticket not found",
        )

    # --------------------------------------------------------
    # Override module
    # --------------------------------------------------------

    if module:
        module_obj = (
            db.query(Module)
            .filter(
                Module.name.ilike(module)
            )
            .first()
        )

        if module_obj is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown module: {module}"
                ),
            )

        ticket_obj.module_id = module_obj.id

    # --------------------------------------------------------
    # Override severity
    # --------------------------------------------------------

    if severity:
        ticket_obj.severity = severity

    ticket_obj.status = "open"
    ticket_obj.review_reasons = None
    ticket_obj.is_open = True

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "ticket_id": ticket_id,
        "status": "open",
        "module": module,
        "severity": severity,
    }