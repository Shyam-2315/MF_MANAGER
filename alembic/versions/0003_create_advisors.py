"""create advisors table

Revision ID: 0003_create_advisors
Revises: 0002_update_user_auth_fields
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_create_advisors"
down_revision: Union[str, None] = "0002_update_user_auth_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "advisors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("firm_name", sa.String(length=255), nullable=False),
        sa.Column("arn_number", sa.String(length=64), nullable=True),
        sa.Column("ria_number", sa.String(length=64), nullable=True),
        sa.Column("license_type", sa.String(length=50), nullable=False),
        sa.Column("target_region", sa.String(length=255), nullable=False),
        sa.Column("business_address", sa.Text(), nullable=False),
        sa.Column("compliance_status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("onboarding_status", sa.String(length=50), server_default="IN_PROGRESS", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("arn_number"),
        sa.UniqueConstraint("ria_number"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_advisors_user_id"), "advisors", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_advisors_user_id"), table_name="advisors")
    op.drop_table("advisors")
