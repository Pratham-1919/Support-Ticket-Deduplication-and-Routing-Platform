from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from pydantic import BaseModel, Field

from src.core.security import get_current_user
from src.core.rate_limit import limiter
from src.services.qa_service import answer_question


router = APIRouter(
    prefix="/qa",
    tags=["Q&A"],
)


# ============================================================
# Request schema
# ============================================================

from src.api.schemas.qa import QuestionRequest

# ============================================================
# Q&A endpoint
# ============================================================

@router.post("/")
@limiter.limit("10/minute")
def ask_question(
    request: Request,
    payload: QuestionRequest,
    current_user: dict = Depends(get_current_user),
):

    try:

        return answer_question(
            question=payload.question
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to answer question: {str(e)}",
        )