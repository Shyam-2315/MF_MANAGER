"""create transactions table

Revision ID: 0007_create_transactions
Revises: 0006_create_sips
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_create_transactions"
down_revision: Union[str, None] = "0006_create_sips"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("advisor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheme_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sip_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "transaction_type",
            sa.Enum("BUY", "SELL", "SIP_INSTALLMENT", "SWITCH_IN", "SWITCH_OUT", "DIVIDEND", native_enum=False, length=50),
            nullable=False,
        ),
        sa.Column(
            "transaction_status",
            sa.Enum("PENDING", "COMPLETED", "FAILED", "CANCELLED", native_enum=False, length=50),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("units", sa.Numeric(18, 4), nullable=False),
        sa.Column("nav", sa.Numeric(12, 4), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settlement_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["advisor_id"], ["advisors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["folio_id"], ["folios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scheme_id"], ["mutual_fund_schemes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sip_id"], ["sips.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint("units > 0", name="ck_transactions_units_positive"),
        sa.CheckConstraint("nav > 0", name="ck_transactions_nav_positive"),
    )
    op.create_index(op.f("ix_transactions_advisor_id"), "transactions", ["advisor_id"], unique=False)
    op.create_index(op.f("ix_transactions_customer_id"), "transactions", ["customer_id"], unique=False)
    op.create_index(op.f("ix_transactions_folio_id"), "transactions", ["folio_id"], unique=False)
    op.create_index(op.f("ix_transactions_scheme_id"), "transactions", ["scheme_id"], unique=False)
    op.create_index(op.f("ix_transactions_sip_id"), "transactions", ["sip_id"], unique=False)
    op.create_index(op.f("ix_transactions_transaction_date"), "transactions", ["transaction_date"], unique=False)
    op.create_index(op.f("ix_transactions_transaction_type"), "transactions", ["transaction_type"], unique=False)
    op.create_index(op.f("ix_transactions_transaction_status"), "transactions", ["transaction_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_transaction_status"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_transaction_type"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_transaction_date"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_sip_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_scheme_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_folio_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_customer_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_advisor_id"), table_name="transactions")
    op.drop_table("transactions")
