"""create nav history table

Revision ID: 0008_create_nav_history
Revises: 0007_create_transactions
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_create_nav_history"
down_revision: Union[str, None] = "0007_create_transactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mutual_fund_nav_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheme_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nav_date", sa.Date(), nullable=False),
        sa.Column("nav_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["scheme_id"], ["mutual_fund_schemes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme_id", "nav_date", name="uq_mutual_fund_nav_scheme_date"),
        sa.CheckConstraint("nav_value > 0", name="ck_mutual_fund_nav_value_positive"),
    )
    op.create_index(op.f("ix_mutual_fund_nav_history_scheme_id"), "mutual_fund_nav_history", ["scheme_id"], unique=False)
    op.create_index(op.f("ix_mutual_fund_nav_history_nav_date"), "mutual_fund_nav_history", ["nav_date"], unique=False)
    op.create_index(
        "ix_mutual_fund_nav_history_scheme_nav_date",
        "mutual_fund_nav_history",
        ["scheme_id", "nav_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mutual_fund_nav_history_scheme_nav_date", table_name="mutual_fund_nav_history")
    op.drop_index(op.f("ix_mutual_fund_nav_history_nav_date"), table_name="mutual_fund_nav_history")
    op.drop_index(op.f("ix_mutual_fund_nav_history_scheme_id"), table_name="mutual_fund_nav_history")
    op.drop_table("mutual_fund_nav_history")
