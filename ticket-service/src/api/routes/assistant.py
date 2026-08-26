from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from pydantic import BaseModel, Field

from src.core.security import get_current_user
from src.core.rate_limit import limiter
from src.services.agentic_assistant import (
    process_ticket_agentically,
)


router = APIRouter(
    prefix="/assistant",
    tags=["Agentic Assistant"],
)


# ============================================================
# Request schema
# ============================================================

from src.api.schemas.assistant import AgentTicketRequest

# ============================================================
# Agentic processing endpoint
# ============================================================

@router.post("/process")
@limiter.limit("10/minute")
def process_ticket(
    request: Request,
    payload: AgentTicketRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Automatically:
      1. checks duplicates
      2. predicts module
      3. predicts severity
      4. evaluates confidence
      5. recommends routing/review
      6. explains the decision
    """

    try:

        return process_ticket_agentically(
            title=payload.title,
            description=payload.description,
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Agentic processing failed: {str(e)}",
        )