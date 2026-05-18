import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomerKycStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class CustomerRiskProfile(str, enum.Enum):
    CONSERVATIVE = "CONSERVATIVE"
    MODERATE = "MODERATE"
    AGGRESSIVE = "AGGRESSIVE"


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("advisor_id", "email", name="uq_customers_advisor_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("advisors.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pan_number: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    kyc_status: Mapped[CustomerKycStatus] = mapped_column(
        Enum(
            CustomerKycStatus,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=50,
        ),
        default=CustomerKycStatus.PENDING,
        server_default=CustomerKycStatus.PENDING.value,
        nullable=False,
    )
    risk_profile: Mapped[CustomerRiskProfile] = mapped_column(
        Enum(
            CustomerRiskProfile,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=50,
        ),
        default=CustomerRiskProfile.MODERATE,
        server_default=CustomerRiskProfile.MODERATE.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
