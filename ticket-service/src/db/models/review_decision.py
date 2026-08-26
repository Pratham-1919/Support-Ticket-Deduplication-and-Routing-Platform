from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from src.db.base import Base


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(Integer, primary_key=True)
    duplicate_link_id = Column(Integer, ForeignKey("duplicate_links.id"))
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    decision_type = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    notes = Column(Text)
    decided_at = Column(DateTime, server_default=func.now())