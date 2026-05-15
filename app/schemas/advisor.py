from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.advisor import AdvisorComplianceStatus, AdvisorLicenseType, AdvisorOnboardingStatus


class AdvisorBase(BaseModel):
    firm_name: str = Field(min_length=2, max_length=255)
    arn_number: str | None = Field(default=None, min_length=3, max_length=64)
    ria_number: str | None = Field(default=None, min_length=3, max_length=64)
    license_type: AdvisorLicenseType
    target_region: str = Field(min_length=2, max_length=255)
    business_address: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def validate_license_numbers(self) -> "AdvisorBase":
        if self.license_type in {AdvisorLicenseType.ARN, AdvisorLicenseType.ARN_RIA} and not self.arn_number:
            raise ValueError("arn_number is required for ARN license types")
        if self.license_type in {AdvisorLicenseType.RIA, AdvisorLicenseType.ARN_RIA} and not self.ria_number:
            raise ValueError("ria_number is required for RIA license types")
        return self


class AdvisorCreate(AdvisorBase):
    pass


class AdvisorUpdate(BaseModel):
    firm_name: str | None = Field(default=None, min_length=2, max_length=255)
    arn_number: str | None = Field(default=None, min_length=3, max_length=64)
    ria_number: str | None = Field(default=None, min_length=3, max_length=64)
    license_type: AdvisorLicenseType | None = None
    target_region: str | None = Field(default=None, min_length=2, max_length=255)
    business_address: str | None = Field(default=None, min_length=5, max_length=2000)
    compliance_status: AdvisorComplianceStatus | None = None
    onboarding_status: AdvisorOnboardingStatus | None = None


class AdvisorRead(AdvisorBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    compliance_status: AdvisorComplianceStatus
    onboarding_status: AdvisorOnboardingStatus
    created_at: datetime
    updated_at: datetime


class AdvisorRecentTransaction(BaseModel):
    id: UUID | str
    customer_id: UUID | str | None = None
    transaction_type: str | None = None
    amount: Decimal = Decimal("0")
    status: str | None = None
    transaction_date: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdvisorDashboardSummary(BaseModel):
    total_customers: int = 0
    total_aum: Decimal = Decimal("0")
    monthly_sip_amount: Decimal = Decimal("0")
    pending_kyc_customers: int = 0
    active_sips: int = 0
    recent_transactions: list[AdvisorRecentTransaction] = Field(default_factory=list)
