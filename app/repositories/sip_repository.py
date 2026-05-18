from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sip import SIP, SIPFrequency, SIPStatus


class SIPRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> SIP:
        sip = SIP(**data)
        self.db.add(sip)
        await self.db.flush()
        return sip

    async def get_by_id(self, sip_id: UUID, *, active_only: bool = True) -> SIP | None:
        statement = select(SIP).where(SIP.id == sip_id)
        if active_only:
            statement = statement.where(SIP.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_advisor(
        self,
        advisor_id: UUID | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        customer_id: UUID | None = None,
        status: SIPStatus | None = None,
        frequency: SIPFrequency | None = None,
        next_due_before: date | None = None,
        active_only: bool = True,
    ) -> list[SIP]:
        statement = select(SIP)
        if active_only:
            statement = statement.where(SIP.is_active.is_(True))
        if advisor_id is not None:
            statement = statement.where(SIP.advisor_id == advisor_id)
        if customer_id is not None:
            statement = statement.where(SIP.customer_id == customer_id)
        if status is not None:
            statement = statement.where(SIP.status == status)
        if frequency is not None:
            statement = statement.where(SIP.frequency == frequency)
        if next_due_before is not None:
            statement = statement.where(SIP.next_due_date.is_not(None), SIP.next_due_date <= next_due_before)
        result = await self.db.execute(statement.order_by(SIP.created_at.desc()).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[SIP]:
        statement = select(SIP).where(SIP.customer_id == customer_id)
        if active_only:
            statement = statement.where(SIP.is_active.is_(True))
        result = await self.db.execute(statement.order_by(SIP.created_at.desc()).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def list_due_sips(
        self,
        *,
        due_before: date,
        advisor_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SIP]:
        return await self.list_by_advisor(
            advisor_id,
            limit=limit,
            offset=offset,
            status=SIPStatus.ACTIVE,
            next_due_before=due_before,
        )

    async def update(self, sip: SIP, data: dict[str, Any]) -> SIP:
        for field, value in data.items():
            setattr(sip, field, value)
        await self.db.flush()
        return sip

    async def soft_delete(self, sip: SIP) -> SIP:
        sip.is_active = False
        await self.db.flush()
        return sip

    async def count_active_sips_for_advisor(self, advisor_id: UUID | None = None) -> int:
        statement = select(func.count(SIP.id)).where(SIP.is_active.is_(True), SIP.status == SIPStatus.ACTIVE)
        if advisor_id is not None:
            statement = statement.where(SIP.advisor_id == advisor_id)
        result = await self.db.execute(statement)
        return int(result.scalar_one() or 0)

    async def sum_monthly_sip_amount_for_advisor(self, advisor_id: UUID | None = None) -> Decimal:
        statement = select(func.coalesce(func.sum(SIP.sip_amount), 0)).where(
            SIP.is_active.is_(True),
            SIP.status == SIPStatus.ACTIVE,
            SIP.frequency == SIPFrequency.MONTHLY,
        )
        if advisor_id is not None:
            statement = statement.where(SIP.advisor_id == advisor_id)
        result = await self.db.execute(statement)
        return Decimal(result.scalar_one() or 0)

    async def customer_sip_summary(self, customer_id: UUID) -> dict[str, Any]:
        status_counts_statement = (
            select(SIP.status, func.count(SIP.id))
            .where(SIP.customer_id == customer_id, SIP.is_active.is_(True))
            .group_by(SIP.status)
        )
        status_counts_result = await self.db.execute(status_counts_statement)
        status_counts = {status: int(count or 0) for status, count in status_counts_result.all()}

        monthly_amount_statement = select(func.coalesce(func.sum(SIP.sip_amount), 0)).where(
            SIP.customer_id == customer_id,
            SIP.is_active.is_(True),
            SIP.status == SIPStatus.ACTIVE,
            SIP.frequency == SIPFrequency.MONTHLY,
        )
        monthly_amount_result = await self.db.execute(monthly_amount_statement)

        next_due_statement = select(func.min(SIP.next_due_date)).where(
            SIP.customer_id == customer_id,
            SIP.is_active.is_(True),
            SIP.status == SIPStatus.ACTIVE,
            SIP.next_due_date.is_not(None),
        )
        next_due_result = await self.db.execute(next_due_statement)

        return {
            "active_sips": status_counts.get(SIPStatus.ACTIVE, 0),
            "paused_sips": status_counts.get(SIPStatus.PAUSED, 0),
            "cancelled_sips": status_counts.get(SIPStatus.CANCELLED, 0),
            "completed_sips": status_counts.get(SIPStatus.COMPLETED, 0),
            "total_monthly_sip_amount": Decimal(monthly_amount_result.scalar_one() or 0),
            "next_due_sip_date": next_due_result.scalar_one_or_none(),
        }
