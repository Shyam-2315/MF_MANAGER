from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.transaction import TransactionStatus, TransactionType


class TransactionBase(BaseModel):
    customer_id: UUID
    advisor_id: UUID | None = None
    folio_id: UUID
    scheme_id: UUID
    sip_id: UUID | None = None
    transaction_type: TransactionType
    transaction_status: TransactionStatus = TransactionStatus.PENDING
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    units: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    nav: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    transaction_date: datetime
    settlement_date: datetime | None = None
    external_reference: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    transaction_status: TransactionStatus | None = None
    settlement_date: datetime | None = None
    external_reference: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    advisor_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TransactionListItem(TransactionRead):
    pass


class CustomerTransactionSummary(BaseModel):
    customer_id: UUID
    total_transactions: int = 0
    total_invested_amount: Decimal = Decimal("0")
    total_sell_amount: Decimal = Decimal("0")
    total_units: Decimal = Decimal("0")
    latest_transaction_date: datetime | None = None
