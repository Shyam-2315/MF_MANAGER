"""create sips table

Revision ID: 0006_create_sips
Revises: 0005_create_portfolio_folio
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_create_sips"
down_revision: Union[str, None] = "0005_create_portfolio_folio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sips",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("advisor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheme_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sip_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("frequency", sa.Enum("MONTHLY", "QUARTERLY", "YEARLY", native_enum=False, length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "PAUSED", "CANCELLED", "COMPLETED", native_enum=False, length=50),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("mandate_reference", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["advisor_id"], ["advisors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["folio_id"], ["folios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scheme_id"], ["mutual_fund_schemes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("sip_amount > 0", name="ck_sips_sip_amount_positive"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_sips_end_date_after_start_date"),
        sa.CheckConstraint(
            "next_due_date IS NULL OR next_due_date >= start_date",
            name="ck_sips_next_due_date_after_start_date",
        ),
    )
    op.create_index(op.f("ix_sips_advisor_id"), "sips", ["advisor_id"], unique=False)
    op.create_index(op.f("ix_sips_customer_id"), "sips", ["customer_id"], unique=False)
    op.create_index(op.f("ix_sips_folio_id"), "sips", ["folio_id"], unique=False)
    op.create_index(op.f("ix_sips_scheme_id"), "sips", ["scheme_id"], unique=False)
    op.create_index(op.f("ix_sips_status"), "sips", ["status"], unique=False)
    op.create_index(op.f("ix_sips_next_due_date"), "sips", ["next_due_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sips_next_due_date"), table_name="sips")
    op.drop_index(op.f("ix_sips_status"), table_name="sips")
    op.drop_index(op.f("ix_sips_scheme_id"), table_name="sips")
    op.drop_index(op.f("ix_sips_folio_id"), table_name="sips")
    op.drop_index(op.f("ix_sips_customer_id"), table_name="sips")
    op.drop_index(op.f("ix_sips_advisor_id"), table_name="sips")
    op.drop_table("sips")
