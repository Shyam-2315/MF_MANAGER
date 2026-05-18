from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_required_string(value: str) -> str:
    return value.strip() if isinstance(value, str) else value


class MutualFundSchemeBase(BaseModel):
    scheme_code: str = Field(min_length=1, max_length=64)
    scheme_name: str = Field(min_length=1, max_length=255)
    amc_name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    sub_category: str | None = Field(default=None, max_length=128)
    risk_level: str | None = Field(default=None, max_length=64)

    @field_validator("scheme_code", mode="before")
    @classmethod
    def normalize_scheme_code(cls, value: str) -> str:
        return _normalize_required_string(value)


class MutualFundSchemeCreate(MutualFundSchemeBase):
    pass


class MutualFundSchemeUpdate(BaseModel):
    scheme_code: str | None = Field(default=None, min_length=1, max_length=64)
    scheme_name: str | None = Field(default=None, min_length=1, max_length=255)
    amc_name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    sub_category: str | None = Field(default=None, max_length=128)
    risk_level: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None

    @field_validator("scheme_code", mode="before")
    @classmethod
    def normalize_scheme_code(cls, value: str | None) -> str | None:
        return _normalize_required_string(value) if value is not None else value


class MutualFundSchemeRead(MutualFundSchemeBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FolioBase(BaseModel):
    customer_id: UUID
    advisor_id: UUID | None = None
    folio_number: str = Field(min_length=1, max_length=128)
    platform: str | None = Field(default=None, max_length=128)

    @field_validator("folio_number", mode="before")
    @classmethod
    def normalize_folio_number(cls, value: str) -> str:
        return _normalize_required_string(value)


class FolioCreate(FolioBase):
    pass


class FolioUpdate(BaseModel):
    folio_number: str | None = Field(default=None, min_length=1, max_length=128)
    platform: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None

    @field_validator("folio_number", mode="before")
    @classmethod
    def normalize_folio_number(cls, value: str | None) -> str | None:
        return _normalize_required_string(value) if value is not None else value


class FolioRead(FolioBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    advisor_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PortfolioHoldingBase(BaseModel):
    folio_id: UUID
    customer_id: UUID
    advisor_id: UUID | None = None
    scheme_id: UUID
    invested_amount: Decimal = Field(default=Decimal("0"), ge=0)
    current_value: Decimal = Field(default=Decimal("0"), ge=0)
    units: Decimal = Field(default=Decimal("0"), ge=0)
    average_nav: Decimal | None = Field(default=None, ge=0)
    current_nav: Decimal | None = Field(default=None, ge=0)
    valuation_date: date | None = None


class PortfolioHoldingCreate(PortfolioHoldingBase):
    pass


class PortfolioHoldingUpdate(BaseModel):
    invested_amount: Decimal | None = Field(default=None, ge=0)
    current_value: Decimal | None = Field(default=None, ge=0)
    units: Decimal | None = Field(default=None, ge=0)
    average_nav: Decimal | None = Field(default=None, ge=0)
    current_nav: Decimal | None = Field(default=None, ge=0)
    valuation_date: date | None = None
    is_active: bool | None = None


class PortfolioHoldingRead(PortfolioHoldingBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    advisor_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PortfolioSummaryRead(BaseModel):
    customer_id: UUID
    total_invested_amount: Decimal = Decimal("0")
    total_current_value: Decimal = Decimal("0")
    total_gain_loss: Decimal = Decimal("0")
    total_gain_loss_percentage: Decimal = Decimal("0")
    holdings_count: int = 0
