import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdvisorLicenseType(str, enum.Enum):
    ARN = "ARN"
    RIA = "RIA"
    ARN_RIA = "ARN_RIA"


class AdvisorComplianceStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AdvisorOnboardingStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class Advisor(Base):
    __tablename__ = "advisors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    firm_name: Mapped[str] = mapped_column(String(255), nullable=False)
    arn_number: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    ria_number: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    license_type: Mapped[AdvisorLicenseType] = mapped_column(
        Enum(
            AdvisorLicenseType,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=50,
        ),
        nullable=False,
    )
    target_region: Mapped[str] = mapped_column(String(255), nullable=False)
    business_address: Mapped[str] = mapped_column(Text, nullable=False)
    compliance_status: Mapped[AdvisorComplianceStatus] = mapped_column(
        Enum(
            AdvisorComplianceStatus,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=50,
        ),
        default=AdvisorComplianceStatus.PENDING,
        server_default=AdvisorComplianceStatus.PENDING.value,
        nullable=False,
    )
    onboarding_status: Mapped[AdvisorOnboardingStatus] = mapped_column(
        Enum(
            AdvisorOnboardingStatus,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=50,
        ),
        default=AdvisorOnboardingStatus.IN_PROGRESS,
        server_default=AdvisorOnboardingStatus.IN_PROGRESS.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
