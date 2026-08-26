# src/api/routes/tickets.py

import os
from typing import Optional
from datetime import datetime, timedelta

import httpx

from pydantic import BaseModel

from fastapi import (
    Request,
    APIRouter,
    HTTPException,
    Depends,
)

from sqlalchemy.orm import Session
from sqlalchemy import (
    func,
    or_,
    cast,
    String,
)

from src.db.session import get_db

from src.db.models.ticket import Ticket
from src.db.models.module import Module
from src.db.models.duplicate_link import DuplicateLink

from src.core.security import (
    require_role,
    get_current_user,
    get_current_user_or_internal,
)

from src.api.schemas import CreateTicketRequest
from src.services.ticket_service import create_ticket
from src.core.rate_limit import limiter


# ============================================================
# Configuration
# ============================================================

DOC_SERVICE_URL = os.getenv(
    "DOC_SERVICE_URL",
    "http://localhost:8001",
)


# IMPORTANT:
# Keep API paths lowercase.
router = APIRouter(
    prefix="/tickets",
    tags=["tickets"],
)


# ============================================================
# Valid ticket statuses
# ============================================================

VALID_STATUSES = {
    "open",
    "pending_review",
    "resolved",
    "closed",
    "closed_as_duplicate",
}

from src.api.schemas.ticket import CreateTicketRequest, UpdateStatusRequest

# ============================================================
# 1. CREATE TICKET
# ============================================================

@router.post("/")
@limiter.limit("20/minute")
def create_new_ticket(
    request: Request,
    payload: CreateTicketRequest,
    db: Session = Depends(get_db),
):
    try:

        return create_ticket(
            db,
            title=payload.title,
            description=payload.description,
            module=payload.module,
            component=payload.component,
            severity=payload.severity,
            priority=payload.priority,
            ticket_type=payload.ticket_type,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# 2. LIST TICKETS
# ============================================================

@router.get("/")
def list_tickets(
    module: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="page must be >= 1",
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="page_size must be between 1 and 100",
        )

    # --------------------------------------------------------
    # Base ORM query
    # --------------------------------------------------------

    query = (
        db.query(
            Ticket,
            Module.name,
        )
        .join(
            Module,
            Ticket.module_id == Module.id,
        )
    )

    # --------------------------------------------------------
    # Optional filters
    # --------------------------------------------------------

    if module:
        query = query.filter(
            Module.name.ilike(module)
        )

    if status:
        query = query.filter(
            Ticket.status == status
        )

    if severity:
        query = query.filter(
            Ticket.severity.ilike(severity)
        )

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    offset = (page - 1) * page_size

    rows = (
        query
        .order_by(Ticket.id.desc())
        .limit(page_size)
        .offset(offset)
        .all()
    )

    return {
        "page": page,
        "page_size": page_size,
        "results": [
            {
                "id": ticket_obj.id,
                "external_id": ticket_obj.external_id,
                "module": module_name,
                "ticket_type": ticket_obj.ticket_type,
                "title": ticket_obj.title,
                "severity": ticket_obj.severity,
                "priority": ticket_obj.priority,
                "status": ticket_obj.status,
                "is_open": ticket_obj.is_open,
            }
            for ticket_obj, module_name in rows
        ],
    }


# ============================================================
# 3. LIST DUPLICATE LINKS
# ============================================================

@router.get("/duplicates")
def list_duplicate_links(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="page must be >= 1",
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=400,
            detail="page_size must be between 1 and 100",
        )

    offset = (page - 1) * page_size

    links = (
        db.query(DuplicateLink)
        .order_by(DuplicateLink.created_at.desc())
        .limit(page_size)
        .offset(offset)
        .all()
    )

    total = db.query(func.count(DuplicateLink.id)).scalar()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "results": [
            {
                "duplicate_link_id": link.id,
                "ticket_id": link.ticket_id,
                "duplicate_of_ticket_id": link.duplicate_of_ticket_id,
                "similarity_score": link.similarity_score,
                "status": link.status,
                "source": link.source,
                "created_at": link.created_at,
            }
            for link in links
        ],
    }

# ============================================================
# 4. WEEKLY TICKET STATISTICS
#
# IMPORTANT:
# Keep static route BEFORE /{ticket_id}
# ============================================================

@router.get("/stats/weekly")
def weekly_stats(
    current_user: dict = Depends(
        get_current_user_or_internal
    ),
    db: Session = Depends(get_db),
):

    cutoff = (
        datetime.utcnow()
        - timedelta(days=7)
    )

    # --------------------------------------------------------
    # Tickets received
    # --------------------------------------------------------

    received = (
        db.query(
            func.count(Ticket.id)
        )
        .filter(
            Ticket.ingested_at >= cutoff
        )
        .scalar()
    )

    # --------------------------------------------------------
    # Duplicates
    # --------------------------------------------------------

    duplicates = (
        db.query(
            func.count(Ticket.id)
        )
        .filter(
            Ticket.ingested_at >= cutoff,
            Ticket.status
            == "closed_as_duplicate",
        )
        .scalar()
    )

    # --------------------------------------------------------
    # Top modules
    # --------------------------------------------------------

    top_modules_rows = (
        db.query(
            Module.name,
            func.count(Ticket.id).label("cnt"),
        )
        .join(
            Ticket,
            Ticket.module_id == Module.id,
        )
        .filter(
            Ticket.ingested_at >= cutoff
        )
        .group_by(
            Module.name
        )
        .order_by(
            func.count(Ticket.id).desc()
        )
        .limit(5)
        .all()
    )

    top_modules = [
        {
            "module": name,
            "count": count,
        }
        for name, count
        in top_modules_rows
    ]

    duplicate_rate = (
        duplicates / received
        if received > 0
        else 0.0
    )

    return {
        "period": "last_7_days",

        # Keep same key your weekly report expects
        "tickets_received": received,

        "duplicates_detected": duplicates,

        "duplicate_rate": round(
            duplicate_rate,
            4,
        ),

        "most_affected_modules": (
            top_modules
        ),
    }


# ============================================================
# 5. GET SINGLE TICKET
#
# Supports:
#   PostgreSQL ID:
#       387451
#
# AND Eclipse external ID:
#       246235
# ============================================================

@router.get("/{ticket_id}")
@limiter.limit("20/minute")
def get_ticket(
    request: Request,
    ticket_id: str,
    current_user: dict = Depends(
        get_current_user_or_internal
    ),
    db: Session = Depends(get_db),
):

    result = (
        db.query(
            Ticket,
            Module.name,
        )
        .join(
            Module,
            Ticket.module_id == Module.id,
        )
        .filter(
            or_(
                Ticket.external_id
                == ticket_id,

                cast(
                    Ticket.id,
                    String,
                )
                == ticket_id,
            )
        )
        .first()
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"ticket '{ticket_id}' "
                f"not found"
            ),
        )

    ticket_obj, module_name = result

    return {
        "id": ticket_obj.id,

        "external_id": (
            ticket_obj.external_id
        ),

        "module": module_name,

        "ticket_type": (
            ticket_obj.ticket_type
        ),

        "title": ticket_obj.title,

        "description": (
            ticket_obj.description
        ),

        "component": (
            ticket_obj.component
        ),

        "severity": (
            ticket_obj.severity
        ),

        "priority": (
            ticket_obj.priority
        ),

        "status": (
            ticket_obj.status
        ),

        "resolution": (
            ticket_obj.resolution
        ),

        "is_open": (
            ticket_obj.is_open
        ),

        "review_reasons": (
            ticket_obj.review_reasons.split(",")
            if ticket_obj.review_reasons
            else []
        ),

        "created_at": (
            ticket_obj.source_created_at
            or ticket_obj.ingested_at
        ),
    }


# ============================================================
# 6. UPDATE TICKET STATUS
# ============================================================

@router.put("/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    payload: UpdateStatusRequest,
    current_user: dict = Depends(
        require_role(
            "admin",
            "support_engineer",
        )
    ),
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Validate status
    # --------------------------------------------------------

    if payload.status not in VALID_STATUSES:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status: "
                f"{payload.status}"
            ),
        )

    # --------------------------------------------------------
    # Find ticket
    # --------------------------------------------------------

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
    # Update
    # --------------------------------------------------------

    ticket_obj.status = payload.status

    ticket_obj.is_open = (
        payload.status
        in (
            "open",
            "pending_review",
        )
    )

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    # --------------------------------------------------------
    # Generate document when lifecycle finishes
    # --------------------------------------------------------

    if payload.status in (
        "resolved",
        "closed",
        "closed_as_duplicate",
    ):

        try:

            response = httpx.post(
                (
                    f"{DOC_SERVICE_URL}"
                    "/documents/ticket-summary"
                ),
                params={
                    "ticket_id": ticket_id
                },
                timeout=10.0,
            )

            response.raise_for_status()

            print(
                f"Summary generated "
                f"for ticket {ticket_id}"
            )

        except Exception as error:

            print(
                f"Warning: Failed to trigger "
                f"document generation for "
                f"ticket {ticket_id}: "
                f"{error}"
            )

    return {
        "ticket_id": ticket_id,
        "status": payload.status,
    }


# ============================================================
# 7. DELETE TICKET
# ============================================================

@router.delete("/{ticket_id}")
def delete_ticket(
    ticket_id: int,
    current_user: dict = Depends(
        require_role("admin")
    ),
    db: Session = Depends(get_db),
):

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

    try:

        db.delete(ticket_obj)

        db.commit()

    except Exception:

        db.rollback()

        raise

    return {
        "ticket_id": ticket_id,
        "deleted": True,
    }