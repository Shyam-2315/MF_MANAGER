from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.customer import CustomerKycStatus, CustomerRiskProfile

PAN_PATTERN = r"^[A-Z]{5}[0-9]{4}[A-Z]$"


class CustomerBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, min_length=7, max_length=32, pattern=r"^\+?[0-9][0-9 .-]{6,31}$")
    pan_number: str = Field(min_length=10, max_length=10, pattern=PAN_PATTERN)
    date_of_birth: date | None = None
    address: str | None = Field(default=None, max_length=2000)
    kyc_status: CustomerKycStatus = CustomerKycStatus.PENDING
    risk_profile: CustomerRiskProfile = CustomerRiskProfile.MODERATE

    @field_validator("pan_number", mode="before")
    @classmethod
    def normalize_pan_number(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class CustomerCreate(CustomerBase):
    advisor_id: UUID | None = None


class CustomerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=32, pattern=r"^\+?[0-9][0-9 .-]{6,31}$")
    pan_number: str | None = Field(default=None, min_length=10, max_length=10, pattern=PAN_PATTERN)
    date_of_birth: date | None = None
    address: str | None = Field(default=None, max_length=2000)
    kyc_status: CustomerKycStatus | None = None
    risk_profile: CustomerRiskProfile | None = None

    @field_validator("pan_number", mode="before")
    @classmethod
    def normalize_pan_number(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    advisor_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerListItem(CustomerRead):
    pass
