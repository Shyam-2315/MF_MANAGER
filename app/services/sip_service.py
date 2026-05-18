from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.customer import Customer
from app.models.portfolio import Folio
from app.models.sip import SIP, SIPFrequency, SIPStatus
from app.models.user import User, UserRole
from app.repositories.advisor_repository import AdvisorRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.portfolio_repository import FolioRepository, MutualFundSchemeRepository
from app.repositories.sip_repository import SIPRepository
from app.schemas.sip import CustomerSIPSummary, SIPCreate, SIPUpdate


class SIPService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.advisors = AdvisorRepository(db)
        self.customers = CustomerRepository(db)
        self.folios = FolioRepository(db)
        self.schemes = MutualFundSchemeRepository(db)
        self.sips = SIPRepository(db)

    async def create_sip(self, current_user: User, payload: SIPCreate) -> SIP:
        self._assert_can_mutate(current_user)
        customer, folio = await self._validate_sip_relationships(current_user, payload)

        data = payload.model_dump()
        data["customer_id"] = customer.id
        data["advisor_id"] = folio.advisor_id
        sip = await self.sips.create(data)
        await self.db.commit()
        await self.db.refresh(sip)
        return sip

    async def list_sips(
        self,
        current_user: User,
        *,
        limit: int = 50,
        offset: int = 0,
        customer_id: UUID | None = None,
        status: SIPStatus | None = None,
        frequency: SIPFrequency | None = None,
        next_due_before: date | None = None,
    ) -> list[SIP]:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        if customer_id is not None:
            await self._assert_can_read_customer(current_user, customer_id)
        return await self.sips.list_by_advisor(
            advisor_id,
            limit=limit,
            offset=offset,
            customer_id=customer_id,
            status=status,
            frequency=frequency,
            next_due_before=next_due_before,
        )

    async def get_sip(self, current_user: User, sip_id: UUID) -> SIP:
        sip = await self.sips.get_by_id(sip_id)
        if sip is None:
            raise NotFoundException("SIP not found")
        await self._assert_can_read_sip(current_user, sip)
        return sip

    async def update_sip(self, current_user: User, sip_id: UUID, payload: SIPUpdate) -> SIP:
        self._assert_can_mutate(current_user)
        sip = await self.get_sip(current_user, sip_id)
        update_data = payload.model_dump(exclude_unset=True)
        self._validate_effective_dates(sip, update_data)
        updated = await self.sips.update(sip, update_data)
        await self.db.commit()
        await self.db.refresh(updated)
        return updated

    async def delete_sip(self, current_user: User, sip_id: UUID) -> None:
        self._assert_can_mutate(current_user)
        sip = await self.get_sip(current_user, sip_id)
        await self.sips.soft_delete(sip)
        await self.db.commit()

    async def customer_sip_summary(self, current_user: User, customer_id: UUID) -> CustomerSIPSummary:
        await self._assert_can_read_customer(current_user, customer_id)
        summary = await self.sips.customer_sip_summary(customer_id)
        return CustomerSIPSummary(customer_id=customer_id, **summary)

    def _assert_can_mutate(self, current_user: User) -> None:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")

    async def _validate_sip_relationships(self, current_user: User, payload: SIPCreate) -> tuple[Customer, Folio]:
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
            raise BadRequestException("SIP customer_id must match folio customer_id")
        if folio.advisor_id != customer.advisor_id:
            raise BadRequestException("Folio advisor_id must match customer advisor ownership")
        if payload.advisor_id is not None and payload.advisor_id != folio.advisor_id:
            raise BadRequestException("SIP advisor_id must match folio advisor_id")

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

    async def _assert_can_read_sip(self, current_user: User, sip: SIP) -> None:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        if advisor_id is not None and sip.advisor_id != advisor_id:
            raise NotFoundException("SIP not found")

    async def _assert_can_read_customer(self, current_user: User, customer_id: UUID) -> None:
        customer = await self.customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundException("Customer not found")
        advisor_id = await self._resolve_read_advisor_id(current_user)
        if advisor_id is not None and customer.advisor_id != advisor_id:
            raise NotFoundException("Customer not found")

    def _validate_effective_dates(self, sip: SIP, update_data: dict) -> None:
        start_date = update_data.get("start_date", sip.start_date)
        end_date = update_data.get("end_date", sip.end_date)
        next_due_date = update_data.get("next_due_date", sip.next_due_date)
        if end_date is not None and end_date < start_date:
            raise BadRequestException("end_date cannot be before start_date")
        if next_due_date is not None and next_due_date < start_date:
            raise BadRequestException("next_due_date cannot be before start_date")
