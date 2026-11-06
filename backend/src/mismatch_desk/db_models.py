from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ReviewCase(Base):
    __tablename__ = "review_cases"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    invoice_number: Mapped[str | None] = mapped_column(String(120))
    supplier_name: Mapped[str | None] = mapped_column(String(250))
    purchase_order_number: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    extraction_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    reconciliation_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decisions: Mapped[list["ReviewDecision"]] = relationship(
        back_populates="case",
        order_by=lambda: (ReviewDecision.created_at, ReviewDecision.id),
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('request_supplier_correction', 'accept_exception', 'keep_on_hold')",
            name="ck_review_decisions_allowed_values",
        ),
        Index("ix_review_decisions_case_created_at", "case_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("review_cases.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    case: Mapped[ReviewCase] = relationship(back_populates="decisions")
