from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.core.rate_limit import limiter
from fastapi import FastAPI, HTTPException
from src.api.routes import review, tickets, modules, auth, qa
from src.api.routes import assistant
from src.api.schemas import (
    NewTicketRequest,
    TicketDecisionResponse,
)
from src.services.ticket_service import (
    process_new_ticket,
)

from src.core.logging_config import setup_logging, logger
setup_logging()



# ============================================================
# Create FastAPI application
# ============================================================

app = FastAPI(
    title="Support Ticket Deduplication API",
    description=(
        "API for checking new support tickets "
        "against historical Eclipse tickets."
    ),
    version="1.0.0",
)


# ============================================================
# Setting the rate limit
# ============================================================

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)



# ============================================================
# Register routers
# ============================================================

app.include_router(review.router)
app.include_router(tickets.router)
app.include_router(auth.router)
app.include_router(modules.router)
app.include_router(qa.router)
app.include_router(assistant.router)

# ============================================================
# Health check
# ============================================================

@app.get("/")
def root():
    return {
        "message": "Support Ticket Deduplication API is running."
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# ============================================================
# New ticket similarity check (dry-run, no persistence)
# ============================================================

@app.post(
    "/tickets/check",
    response_model=TicketDecisionResponse,
)
def check_ticket(ticket: NewTicketRequest):
    try:
        result = process_new_ticket(
            title=ticket.title,
            description=ticket.description,
            module=ticket.module,
            component=ticket.component,
        )
        return result
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )