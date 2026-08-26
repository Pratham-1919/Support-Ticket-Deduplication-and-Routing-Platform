from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.base import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    external_id = Column(String, unique=True, nullable=False)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)
    ticket_type = Column(String, nullable=False)

    title = Column(Text)
    description = Column(Text)

    classification = Column(Text)
    component = Column(Text)
    product = Column(Text)
    version = Column(Text)
    severity = Column(Text)
    priority = Column(Text)
    status = Column(Text)
    resolution = Column(Text)

    creator = Column(Text)
    assigned_to = Column(Text)

    is_confirmed = Column(Boolean, default=False)
    is_open = Column(Boolean, default=True)

    review_reasons = Column(Text)

    source_created_at = Column(DateTime)
    source_updated_at = Column(DateTime)
    ingested_at = Column(DateTime, server_default=func.now())

    module = relationship("Module", back_populates="tickets")

    duplicate_links = relationship(
        "DuplicateLink",
        foreign_keys="DuplicateLink.ticket_id",
        back_populates="ticket",
    )