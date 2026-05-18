"""create customers table

Revision ID: 0004_create_customers
Revises: 0003_create_advisors
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_create_customers"
down_revision: Union[str, None] = "0003_create_advisors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("advisor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("pan_number", sa.String(length=10), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("kyc_status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("risk_profile", sa.String(length=50), server_default="MODERATE", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["advisor_id"], ["advisors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("advisor_id", "email", name="uq_customers_advisor_email"),
        sa.UniqueConstraint("pan_number"),
    )
    op.create_index(op.f("ix_customers_advisor_id"), "customers", ["advisor_id"], unique=False)
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=False)
    op.create_index(op.f("ix_customers_pan_number"), "customers", ["pan_number"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_customers_pan_number"), table_name="customers")
    op.drop_index(op.f("ix_customers_email"), table_name="customers")
    op.drop_index(op.f("ix_customers_advisor_id"), table_name="customers")
    op.drop_table("customers")
