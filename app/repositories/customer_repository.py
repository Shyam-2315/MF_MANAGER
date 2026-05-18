from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, CustomerKycStatus, CustomerRiskProfile


class CustomerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_customer(self, *, advisor_id: UUID, data: dict[str, Any]) -> Customer:
        data.pop("advisor_id", None)
        customer = Customer(advisor_id=advisor_id, **self._normalize_data(data))
        self.db.add(customer)
        await self.db.flush()
        return customer

    async def get_by_id(self, customer_id: UUID, *, active_only: bool = True) -> Customer | None:
        statement = select(Customer).where(Customer.id == customer_id)
        if active_only:
            statement = statement.where(Customer.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_pan(self, pan_number: str, *, active_only: bool = True) -> Customer | None:
        statement = select(Customer).where(Customer.pan_number == pan_number.upper())
        if active_only:
            statement = statement.where(Customer.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_email_for_advisor(
        self,
        *,
        advisor_id: UUID,
        email: str,
        active_only: bool = True,
    ) -> Customer | None:
        statement = select(Customer).where(Customer.advisor_id == advisor_id, Customer.email == email.lower())
        if active_only:
            statement = statement.where(Customer.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def list_customers(
        self,
        *,
        advisor_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
        kyc_status: CustomerKycStatus | None = None,
        risk_profile: CustomerRiskProfile | None = None,
        search: str | None = None,
        active_only: bool = True,
    ) -> list[Customer]:
        statement = select(Customer)
        if active_only:
            statement = statement.where(Customer.is_active.is_(True))
        if advisor_id is not None:
            statement = statement.where(Customer.advisor_id == advisor_id)
        if kyc_status is not None:
            statement = statement.where(Customer.kyc_status == kyc_status)
        if risk_profile is not None:
            statement = statement.where(Customer.risk_profile == risk_profile)
        if search:
            search_value = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Customer.full_name.ilike(search_value),
                    Customer.email.ilike(search_value),
                    Customer.pan_number.ilike(search_value.upper()),
                )
            )

        statement = statement.order_by(Customer.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def update_customer(self, customer: Customer, data: dict[str, Any]) -> Customer:
        for field, value in self._normalize_data(data).items():
            setattr(customer, field, value)
        await self.db.flush()
        return customer

    async def soft_delete_customer(self, customer: Customer) -> Customer:
        customer.is_active = False
        await self.db.flush()
        return customer

    async def count_customers_for_advisor(self, advisor_id: UUID | None = None) -> int:
        statement = select(func.count()).select_from(Customer).where(Customer.is_active.is_(True))
        if advisor_id is not None:
            statement = statement.where(Customer.advisor_id == advisor_id)
        result = await self.db.execute(statement)
        return int(result.scalar_one() or 0)

    async def count_pending_kyc_for_advisor(self, advisor_id: UUID | None = None) -> int:
        statement = (
            select(func.count())
            .select_from(Customer)
            .where(Customer.is_active.is_(True), Customer.kyc_status == CustomerKycStatus.PENDING)
        )
        if advisor_id is not None:
            statement = statement.where(Customer.advisor_id == advisor_id)
        result = await self.db.execute(statement)
        return int(result.scalar_one() or 0)

    def _normalize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        if normalized.get("email") is not None:
            normalized["email"] = str(normalized["email"]).lower()
        if normalized.get("pan_number") is not None:
            normalized["pan_number"] = str(normalized["pan_number"]).upper()
        return normalized
