from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.base import Base


class DuplicateLink(Base):
    __tablename__ = "duplicate_links"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    duplicate_of_ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    source = Column(String, nullable=False)
    similarity_score = Column(Float)
    status = Column(String, nullable=False, server_default="confirmed")
    created_at = Column(DateTime, server_default=func.now())

    ticket = relationship(
        "Ticket",
        foreign_keys=[ticket_id],
        back_populates="duplicate_links",
    )
    duplicate_of_ticket = relationship(
        "Ticket",
        foreign_keys=[duplicate_of_ticket_id],
    )