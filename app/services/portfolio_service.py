from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.customer import Customer
from app.models.portfolio import Folio, MutualFundScheme, PortfolioHolding
from app.models.user import User, UserRole
from app.repositories.advisor_repository import AdvisorRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.portfolio_repository import (
    FolioRepository,
    MutualFundNAVRepository,
    MutualFundSchemeRepository,
    PortfolioHoldingRepository,
)
from app.schemas.portfolio import (
    FolioCreate,
    FolioUpdate,
    HoldingValuationRecalculationRead,
    MutualFundSchemeCreate,
    MutualFundSchemeUpdate,
    PortfolioHoldingCreate,
    PortfolioHoldingUpdate,
    PortfolioSummaryRead,
)


class MutualFundSchemeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.schemes = MutualFundSchemeRepository(db)

    async def create_scheme(self, current_user: User, payload: MutualFundSchemeCreate) -> MutualFundScheme:
        self._assert_can_mutate(current_user)
        if await self.schemes.get_by_scheme_code(payload.scheme_code) is not None:
            raise BadRequestException("A scheme with this scheme_code already exists")
        try:
            scheme = await self.schemes.create(payload.model_dump())
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("A scheme with this scheme_code already exists") from exc
        await self.db.refresh(scheme)
        return scheme

    async def list_schemes(self, current_user: User, *, limit: int = 50, offset: int = 0) -> list[MutualFundScheme]:
        self._assert_can_read(current_user)
        return await self.schemes.list(limit=limit, offset=offset)

    async def get_scheme(self, current_user: User, scheme_id: UUID) -> MutualFundScheme:
        self._assert_can_read(current_user)
        scheme = await self.schemes.get_by_id(scheme_id)
        if scheme is None:
            raise NotFoundException("Scheme not found")
        return scheme

    async def update_scheme(self, current_user: User, scheme_id: UUID, payload: MutualFundSchemeUpdate) -> MutualFundScheme:
        self._assert_can_mutate(current_user)
        scheme = await self.get_scheme(current_user, scheme_id)
        update_data = payload.model_dump(exclude_unset=True)
        if "scheme_code" in update_data:
            existing = await self.schemes.get_by_scheme_code(update_data["scheme_code"])
            if existing is not None and existing.id != scheme.id:
                raise BadRequestException("A scheme with this scheme_code already exists")
        try:
            updated = await self.schemes.update(scheme, update_data)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("A scheme with this scheme_code already exists") from exc
        await self.db.refresh(updated)
        return updated

    async def delete_scheme(self, current_user: User, scheme_id: UUID) -> None:
        self._assert_can_mutate(current_user)
        scheme = await self.get_scheme(current_user, scheme_id)
        await self.schemes.soft_delete(scheme)
        await self.db.commit()

    def _assert_can_read(self, current_user: User) -> None:
        if current_user.role not in {UserRole.SUPER_ADMIN, UserRole.ADVISOR, UserRole.COMPLIANCE}:
            raise ForbiddenException("Insufficient permissions")

    def _assert_can_mutate(self, current_user: User) -> None:
        if current_user.role != UserRole.SUPER_ADMIN:
            raise ForbiddenException("Insufficient permissions")


class FolioService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.advisors = AdvisorRepository(db)
        self.customers = CustomerRepository(db)
        self.folios = FolioRepository(db)

    async def create_folio(self, current_user: User, payload: FolioCreate) -> Folio:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")

        customer = await self._get_customer_for_write(current_user, payload.customer_id)
        advisor_id = self._resolve_payload_advisor_id(payload.advisor_id, customer.advisor_id)
        if advisor_id != customer.advisor_id:
            raise BadRequestException("Folio advisor_id must match customer advisor ownership")
        if await self.folios.get_by_folio_number_for_customer(
            customer_id=customer.id,
            folio_number=payload.folio_number,
        ):
            raise BadRequestException("A folio with this folio_number already exists for this customer")

        data = payload.model_dump()
        data["advisor_id"] = advisor_id
        try:
            folio = await self.folios.create(data)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("A folio with this folio_number already exists for this customer") from exc
        await self.db.refresh(folio)
        return folio

    async def list_folios(self, current_user: User, *, limit: int = 50, offset: int = 0) -> list[Folio]:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        return await self.folios.list_by_advisor(advisor_id, limit=limit, offset=offset)

    async def get_folio(self, current_user: User, folio_id: UUID) -> Folio:
        folio = await self.folios.get_by_id(folio_id)
        if folio is None:
            raise NotFoundException("Folio not found")
        await self._assert_can_read_folio(current_user, folio)
        return folio

    async def update_folio(self, current_user: User, folio_id: UUID, payload: FolioUpdate) -> Folio:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")
        folio = await self.get_folio(current_user, folio_id)
        update_data = payload.model_dump(exclude_unset=True)
        if "folio_number" in update_data:
            existing = await self.folios.get_by_folio_number_for_customer(
                customer_id=folio.customer_id,
                folio_number=update_data["folio_number"],
            )
            if existing is not None and existing.id != folio.id:
                raise BadRequestException("A folio with this folio_number already exists for this customer")
        try:
            updated = await self.folios.update(folio, update_data)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("A folio with this folio_number already exists for this customer") from exc
        await self.db.refresh(updated)
        return updated

    async def delete_folio(self, current_user: User, folio_id: UUID) -> None:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")
        folio = await self.get_folio(current_user, folio_id)
        await self.folios.soft_delete(folio)
        await self.db.commit()

    async def _get_customer_for_write(self, current_user: User, customer_id: UUID) -> Customer:
        customer = await self.customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundException("Customer not found")
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            if customer.advisor_id != advisor.id:
                raise NotFoundException("Customer not found")
        return customer

    async def _resolve_read_advisor_id(self, current_user: User) -> UUID | None:
        if current_user.role in {UserRole.SUPER_ADMIN, UserRole.COMPLIANCE}:
            return None
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            return advisor.id
        raise ForbiddenException("Insufficient permissions")

    async def _assert_can_read_folio(self, current_user: User, folio: Folio) -> None:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        if advisor_id is not None and folio.advisor_id != advisor_id:
            raise NotFoundException("Folio not found")

    def _resolve_payload_advisor_id(self, requested_advisor_id: UUID | None, customer_advisor_id: UUID) -> UUID:
        return requested_advisor_id or customer_advisor_id


class PortfolioHoldingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.advisors = AdvisorRepository(db)
        self.customers = CustomerRepository(db)
        self.folios = FolioRepository(db)
        self.holdings = PortfolioHoldingRepository(db)
        self.schemes = MutualFundSchemeRepository(db)
        self.navs = MutualFundNAVRepository(db)

    async def create_holding(self, current_user: User, payload: PortfolioHoldingCreate) -> PortfolioHolding:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")

        customer, folio = await self._validate_holding_relationships(current_user, payload)
        if await self.holdings.get_by_folio_and_scheme(folio_id=folio.id, scheme_id=payload.scheme_id):
            raise BadRequestException("An active holding already exists for this folio and scheme")

        data = payload.model_dump()
        data["advisor_id"] = folio.advisor_id
        data["customer_id"] = customer.id
        try:
            holding = await self.holdings.create(data)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("An active holding already exists for this folio and scheme") from exc
        await self.db.refresh(holding)
        return holding

    async def list_holdings(self, current_user: User, *, limit: int = 50, offset: int = 0) -> list[PortfolioHolding]:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        return await self.holdings.list_by_advisor(advisor_id, limit=limit, offset=offset)

    async def get_holding(self, current_user: User, holding_id: UUID) -> PortfolioHolding:
        holding = await self.holdings.get_by_id(holding_id)
        if holding is None:
            raise NotFoundException("Holding not found")
        await self._assert_can_read_holding(current_user, holding)
        return holding

    async def update_holding(
        self,
        current_user: User,
        holding_id: UUID,
        payload: PortfolioHoldingUpdate,
    ) -> PortfolioHolding:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")
        holding = await self.get_holding(current_user, holding_id)
        updated = await self.holdings.update(holding, payload.model_dump(exclude_unset=True))
        await self.db.commit()
        await self.db.refresh(updated)
        return updated

    async def delete_holding(self, current_user: User, holding_id: UUID) -> None:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")
        holding = await self.get_holding(current_user, holding_id)
        await self.holdings.soft_delete(holding)
        await self.db.commit()

    async def customer_portfolio_summary(self, current_user: User, customer_id: UUID) -> PortfolioSummaryRead:
        customer = await self.customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundException("Customer not found")
        if current_user.role == UserRole.CUSTOMER:
            raise ForbiddenException("Insufficient permissions")
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            if customer.advisor_id != advisor.id:
                raise NotFoundException("Customer not found")
        elif current_user.role not in {UserRole.SUPER_ADMIN, UserRole.COMPLIANCE}:
            raise ForbiddenException("Insufficient permissions")

        summary = await self.holdings.calculate_customer_portfolio_summary(customer_id)
        return PortfolioSummaryRead(customer_id=customer_id, **summary)

    async def recalculate_valuations(self, current_user: User) -> HoldingValuationRecalculationRead:
        if current_user.role == UserRole.SUPER_ADMIN:
            advisor_id = None
        elif current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            advisor_id = advisor.id
        else:
            raise ForbiddenException("Insufficient permissions")

        holdings = await self.holdings.list_active_for_valuation(advisor_id)
        holdings_updated = 0
        total_current_value = Decimal("0")
        valuation_date = None
        latest_by_scheme: dict[UUID, tuple[Decimal, date]] = {}

        for holding in holdings:
            nav_tuple = latest_by_scheme.get(holding.scheme_id)
            if nav_tuple is None:
                latest_nav = await self.navs.get_latest_nav_for_scheme(holding.scheme_id)
                if latest_nav is None:
                    total_current_value += Decimal(holding.current_value or 0)
                    continue
                nav_tuple = (Decimal(latest_nav.nav_value), latest_nav.nav_date)
                latest_by_scheme[holding.scheme_id] = nav_tuple
            nav_value, nav_date = nav_tuple
            holding.current_nav = nav_value
            holding.valuation_date = nav_date
            holding.current_value = Decimal(holding.units) * nav_value
            total_current_value += Decimal(holding.current_value)
            if valuation_date is None or nav_date > valuation_date:
                valuation_date = nav_date
            holdings_updated += 1

        await self.db.commit()
        return HoldingValuationRecalculationRead(
            holdings_updated=holdings_updated,
            total_current_value=total_current_value,
            valuation_date=valuation_date,
        )

    async def _validate_holding_relationships(
        self,
        current_user: User,
        payload: PortfolioHoldingCreate,
    ) -> tuple[Customer, Folio]:
        customer = await self.customers.get_by_id(payload.customer_id)
        if customer is None:
            raise NotFoundException("Customer not found")
        folio = await self.folios.get_by_id(payload.folio_id)
        if folio is None:
            raise NotFoundException("Folio not found")
        scheme = await self.schemes.get_by_id(payload.scheme_id)
        if scheme is None:
            raise NotFoundException("Scheme not found")
        if folio.customer_id != customer.id:
            raise BadRequestException("Holding customer_id must match folio customer_id")
        if folio.advisor_id != customer.advisor_id:
            raise BadRequestException("Folio advisor_id must match customer advisor ownership")
        if payload.advisor_id is not None and payload.advisor_id != folio.advisor_id:
            raise BadRequestException("Holding advisor_id must match folio advisor_id")
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            if folio.advisor_id != advisor.id:
                raise NotFoundException("Folio not found")
        return customer, folio

    async def _resolve_read_advisor_id(self, current_user: User) -> UUID | None:
        if current_user.role in {UserRole.SUPER_ADMIN, UserRole.COMPLIANCE}:
            return None
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            return advisor.id
        raise ForbiddenException("Insufficient permissions")

    async def _assert_can_read_holding(self, current_user: User, holding: PortfolioHolding) -> None:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        if advisor_id is not None and holding.advisor_id != advisor_id:
            raise NotFoundException("Holding not found")


def calculate_gain_loss_percentage(invested: Decimal, gain_loss: Decimal) -> Decimal:
    return (gain_loss / invested * Decimal("100")) if invested else Decimal("0")
