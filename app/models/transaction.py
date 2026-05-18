import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TransactionType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    SIP_INSTALLMENT = "SIP_INSTALLMENT"
    SWITCH_IN = "SWITCH_IN"
    SWITCH_OUT = "SWITCH_OUT"
    DIVIDEND = "DIVIDEND"


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvestmentTransaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("advisors.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    folio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folios.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mutual_fund_schemes.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    sip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sips.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=50,
        ),
        index=True,
        nullable=False,
    )
    transaction_status: Mapped[TransactionStatus] = mapped_column(
        Enum(
            TransactionStatus,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=50,
        ),
        default=TransactionStatus.PENDING,
        server_default=TransactionStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    units: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    settlement_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
