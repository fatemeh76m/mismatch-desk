"""Create review cases and immutable decision history.

Revision ID: 20261106_01
Revises:
Create Date: 2026-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261106_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=120), nullable=True),
        sa.Column("supplier_name", sa.String(length=250), nullable=True),
        sa.Column("purchase_order_number", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("extraction_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reconciliation_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewer_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "decision IN ('request_supplier_correction', 'accept_exception', 'keep_on_hold')",
            name="ck_review_decisions_allowed_values",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["review_cases.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_review_decisions_case_created_at",
        "review_decisions",
        ["case_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_decisions_case_created_at", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_table("review_cases")
