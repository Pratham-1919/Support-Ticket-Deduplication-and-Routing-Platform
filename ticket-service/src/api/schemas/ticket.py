from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ModuleName(str, Enum):
    BIRT = "BIRT"
    CDT = "CDT"
    Equinox = "Equinox"
    JDT = "JDT"
    Mylyn = "Mylyn"
    Papyrus = "Papyrus"
    PDE = "PDE"
    Platform = "Platform"
    TPTP = "TPTP"


class NewTicketRequest(BaseModel):
    """Used by /tickets/check -- a dry-run duplicate check, no persistence."""
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    module: Optional[str] = None
    component: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None


class CreateTicketRequest(BaseModel):
    """Used by POST /tickets/ -- creates the ticket and persists a duplicate_links row if matched."""
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    module: Optional[ModuleName] = None
    component: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None
    ticket_type: str = "bug_report"   # or "feature_request"


class UpdateStatusRequest(BaseModel):
    """Used by PUT /tickets/{ticket_id}/status."""
    status: str


class SimilarTicket(BaseModel):
    """A ticket returned from ChromaDB similarity search."""
    ticket_id: str
    similarity_score: float
    title: Optional[str] = None
    description: Optional[str] = None


class TicketDecisionResponse(BaseModel):
    """Response for /tickets/check."""
    decision: str
    message: str
    similarity_score: Optional[float] = None
    matched_ticket: Optional[SimilarTicket] = None