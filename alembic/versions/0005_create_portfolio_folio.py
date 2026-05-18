"""create portfolio folio tables

Revision ID: 0005_create_portfolio_folio
Revises: 0004_create_customers
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_create_portfolio_folio"
down_revision: Union[str, None] = "0004_create_customers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mutual_fund_schemes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheme_code", sa.String(length=64), nullable=False),
        sa.Column("scheme_name", sa.String(length=255), nullable=False),
        sa.Column("amc_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("sub_category", sa.String(length=128), nullable=True),
        sa.Column("risk_level", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme_code"),
    )
    op.create_index(op.f("ix_mutual_fund_schemes_scheme_code"), "mutual_fund_schemes", ["scheme_code"], unique=True)

    op.create_table(
        "folios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("advisor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folio_number", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["advisor_id"], ["advisors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "folio_number", name="uq_folios_customer_folio_number"),
    )
    op.create_index(op.f("ix_folios_advisor_id"), "folios", ["advisor_id"], unique=False)
    op.create_index(op.f("ix_folios_customer_id"), "folios", ["customer_id"], unique=False)

    op.create_table(
        "portfolio_holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("advisor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheme_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invested_amount", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("current_value", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("units", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("average_nav", sa.Numeric(12, 4), nullable=True),
        sa.Column("current_nav", sa.Numeric(12, 4), nullable=True),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["advisor_id"], ["advisors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["folio_id"], ["folios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scheme_id"], ["mutual_fund_schemes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_holdings_advisor_id"), "portfolio_holdings", ["advisor_id"], unique=False)
    op.create_index(op.f("ix_portfolio_holdings_customer_id"), "portfolio_holdings", ["customer_id"], unique=False)
    op.create_index(op.f("ix_portfolio_holdings_folio_id"), "portfolio_holdings", ["folio_id"], unique=False)
    op.create_index(op.f("ix_portfolio_holdings_scheme_id"), "portfolio_holdings", ["scheme_id"], unique=False)
    op.create_index(
        "uq_portfolio_holdings_active_folio_scheme",
        "portfolio_holdings",
        ["folio_id", "scheme_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_portfolio_holdings_active_folio_scheme", table_name="portfolio_holdings")
    op.drop_index(op.f("ix_portfolio_holdings_scheme_id"), table_name="portfolio_holdings")
    op.drop_index(op.f("ix_portfolio_holdings_folio_id"), table_name="portfolio_holdings")
    op.drop_index(op.f("ix_portfolio_holdings_customer_id"), table_name="portfolio_holdings")
    op.drop_index(op.f("ix_portfolio_holdings_advisor_id"), table_name="portfolio_holdings")
    op.drop_table("portfolio_holdings")
    op.drop_index(op.f("ix_folios_customer_id"), table_name="folios")
    op.drop_index(op.f("ix_folios_advisor_id"), table_name="folios")
    op.drop_table("folios")
    op.drop_index(op.f("ix_mutual_fund_schemes_scheme_code"), table_name="mutual_fund_schemes")
    op.drop_table("mutual_fund_schemes")
