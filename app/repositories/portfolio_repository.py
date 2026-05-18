from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Folio, MutualFundScheme, PortfolioHolding


class MutualFundSchemeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> MutualFundScheme:
        scheme = MutualFundScheme(**self._normalize_data(data))
        self.db.add(scheme)
        await self.db.flush()
        return scheme

    async def get_by_id(self, scheme_id: UUID, *, active_only: bool = True) -> MutualFundScheme | None:
        statement = select(MutualFundScheme).where(MutualFundScheme.id == scheme_id)
        if active_only:
            statement = statement.where(MutualFundScheme.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_scheme_code(self, scheme_code: str, *, active_only: bool = True) -> MutualFundScheme | None:
        statement = select(MutualFundScheme).where(MutualFundScheme.scheme_code == scheme_code.strip())
        if active_only:
            statement = statement.where(MutualFundScheme.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def list(self, *, limit: int = 50, offset: int = 0, active_only: bool = True) -> list[MutualFundScheme]:
        statement = select(MutualFundScheme)
        if active_only:
            statement = statement.where(MutualFundScheme.is_active.is_(True))
        statement = statement.order_by(MutualFundScheme.scheme_name.asc()).limit(limit).offset(offset)
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def update(self, scheme: MutualFundScheme, data: dict[str, Any]) -> MutualFundScheme:
        for field, value in self._normalize_data(data).items():
            setattr(scheme, field, value)
        await self.db.flush()
        return scheme

    async def soft_delete(self, scheme: MutualFundScheme) -> MutualFundScheme:
        scheme.is_active = False
        await self.db.flush()
        return scheme

    def _normalize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        if normalized.get("scheme_code") is not None:
            normalized["scheme_code"] = str(normalized["scheme_code"]).strip()
        return normalized


class FolioRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> Folio:
        folio = Folio(**self._normalize_data(data))
        self.db.add(folio)
        await self.db.flush()
        return folio

    async def get_by_id(self, folio_id: UUID, *, active_only: bool = True) -> Folio | None:
        statement = select(Folio).where(Folio.id == folio_id)
        if active_only:
            statement = statement.where(Folio.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_customer_id(self, customer_id: UUID, *, active_only: bool = True) -> list[Folio]:
        statement = select(Folio).where(Folio.customer_id == customer_id)
        if active_only:
            statement = statement.where(Folio.is_active.is_(True))
        result = await self.db.execute(statement.order_by(Folio.created_at.desc()))
        return list(result.scalars().all())

    async def get_by_folio_number_for_customer(
        self,
        *,
        customer_id: UUID,
        folio_number: str,
        active_only: bool = True,
    ) -> Folio | None:
        statement = select(Folio).where(Folio.customer_id == customer_id, Folio.folio_number == folio_number.strip())
        if active_only:
            statement = statement.where(Folio.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_advisor(
        self,
        advisor_id: UUID | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[Folio]:
        statement = select(Folio)
        if active_only:
            statement = statement.where(Folio.is_active.is_(True))
        if advisor_id is not None:
            statement = statement.where(Folio.advisor_id == advisor_id)
        result = await self.db.execute(statement.order_by(Folio.created_at.desc()).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def update(self, folio: Folio, data: dict[str, Any]) -> Folio:
        for field, value in self._normalize_data(data).items():
            setattr(folio, field, value)
        await self.db.flush()
        return folio

    async def soft_delete(self, folio: Folio) -> Folio:
        folio.is_active = False
        await self.db.flush()
        return folio

    def _normalize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        if normalized.get("folio_number") is not None:
            normalized["folio_number"] = str(normalized["folio_number"]).strip()
        return normalized


class PortfolioHoldingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> PortfolioHolding:
        holding = PortfolioHolding(**data)
        self.db.add(holding)
        await self.db.flush()
        return holding

    async def get_by_id(self, holding_id: UUID, *, active_only: bool = True) -> PortfolioHolding | None:
        statement = select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
        if active_only:
            statement = statement.where(PortfolioHolding.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_folio_and_scheme(
        self,
        *,
        folio_id: UUID,
        scheme_id: UUID,
        active_only: bool = True,
    ) -> PortfolioHolding | None:
        statement = select(PortfolioHolding).where(
            PortfolioHolding.folio_id == folio_id,
            PortfolioHolding.scheme_id == scheme_id,
        )
        if active_only:
            statement = statement.where(PortfolioHolding.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[PortfolioHolding]:
        statement = select(PortfolioHolding).where(PortfolioHolding.customer_id == customer_id)
        if active_only:
            statement = statement.where(PortfolioHolding.is_active.is_(True))
        result = await self.db.execute(statement.order_by(PortfolioHolding.created_at.desc()).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def list_by_advisor(
        self,
        advisor_id: UUID | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[PortfolioHolding]:
        statement = select(PortfolioHolding)
        if active_only:
            statement = statement.where(PortfolioHolding.is_active.is_(True))
        if advisor_id is not None:
            statement = statement.where(PortfolioHolding.advisor_id == advisor_id)
        result = await self.db.execute(statement.order_by(PortfolioHolding.created_at.desc()).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def update(self, holding: PortfolioHolding, data: dict[str, Any]) -> PortfolioHolding:
        for field, value in data.items():
            setattr(holding, field, value)
        await self.db.flush()
        return holding

    async def soft_delete(self, holding: PortfolioHolding) -> PortfolioHolding:
        holding.is_active = False
        await self.db.flush()
        return holding

    async def calculate_customer_portfolio_summary(self, customer_id: UUID) -> dict[str, Decimal | int]:
        statement = (
            select(
                func.coalesce(func.sum(PortfolioHolding.invested_amount), 0),
                func.coalesce(func.sum(PortfolioHolding.current_value), 0),
                func.count(PortfolioHolding.id),
            )
            .select_from(PortfolioHolding)
            .where(PortfolioHolding.customer_id == customer_id, PortfolioHolding.is_active.is_(True))
        )
        result = await self.db.execute(statement)
        invested_amount, current_value, holdings_count = result.one()
        invested = Decimal(invested_amount or 0)
        current = Decimal(current_value or 0)
        gain_loss = current - invested
        percentage = (gain_loss / invested * Decimal("100")) if invested else Decimal("0")
        return {
            "total_invested_amount": invested,
            "total_current_value": current,
            "total_gain_loss": gain_loss,
            "total_gain_loss_percentage": percentage,
            "holdings_count": int(holdings_count or 0),
        }

    async def calculate_advisor_total_aum(self, advisor_id: UUID | None = None) -> Decimal:
        statement = select(func.coalesce(func.sum(PortfolioHolding.current_value), 0)).where(
            PortfolioHolding.is_active.is_(True)
        )
        if advisor_id is not None:
            statement = statement.where(PortfolioHolding.advisor_id == advisor_id)
        result = await self.db.execute(statement)
        return Decimal(result.scalar_one() or 0)
