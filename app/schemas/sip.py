from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.sip import SIPFrequency, SIPStatus


class SIPBase(BaseModel):
    customer_id: UUID
    advisor_id: UUID | None = None
    folio_id: UUID
    scheme_id: UUID
    sip_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    frequency: SIPFrequency
    status: SIPStatus = SIPStatus.ACTIVE
    start_date: date
    end_date: date | None = None
    next_due_date: date | None = None
    mandate_reference: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_dates(self) -> "SIPBase":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        if self.next_due_date is not None and self.next_due_date < self.start_date:
            raise ValueError("next_due_date cannot be before start_date")
        return self


class SIPCreate(SIPBase):
    pass


class SIPUpdate(BaseModel):
    sip_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    frequency: SIPFrequency | None = None
    status: SIPStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    next_due_date: date | None = None
    mandate_reference: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class SIPRead(SIPBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    advisor_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SIPListItem(SIPRead):
    pass


class CustomerSIPSummary(BaseModel):
    customer_id: UUID
    active_sips: int = 0
    paused_sips: int = 0
    cancelled_sips: int = 0
    completed_sips: int = 0
    total_monthly_sip_amount: Decimal = Decimal("0")
    next_due_sip_date: date | None = None
