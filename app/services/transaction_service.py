from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.customer import Customer
from app.models.portfolio import Folio, PortfolioHolding
from app.models.transaction import InvestmentTransaction, TransactionStatus, TransactionType
from app.models.user import User, UserRole
from app.repositories.advisor_repository import AdvisorRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.portfolio_repository import FolioRepository, MutualFundSchemeRepository, PortfolioHoldingRepository
from app.repositories.sip_repository import SIPRepository
from app.repositories.transaction_repository import InvestmentTransactionRepository
from app.schemas.transaction import CustomerTransactionSummary, TransactionCreate, TransactionUpdate


INFLOW_TYPES = {TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN}
OUTFLOW_TYPES = {TransactionType.SELL, TransactionType.SWITCH_OUT}


class InvestmentTransactionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.advisors = AdvisorRepository(db)
        self.customers = CustomerRepository(db)
        self.folios = FolioRepository(db)
        self.schemes = MutualFundSchemeRepository(db)
        self.sips = SIPRepository(db)
        self.holdings = PortfolioHoldingRepository(db)
        self.transactions = InvestmentTransactionRepository(db)

    async def create_transaction(
        self,
        current_user: User,
        payload: TransactionCreate,
    ) -> InvestmentTransaction:
        self._assert_can_mutate(current_user)
        customer, folio = await self._validate_transaction_relationships(current_user, payload)

        if payload.transaction_type in OUTFLOW_TYPES:
            available_units = await self._available_units(customer_id=customer.id, folio_id=folio.id, scheme_id=payload.scheme_id)
            if payload.units > available_units:
                raise BadRequestException("Transaction units exceed available holding units")

        data = payload.model_dump()
        data["customer_id"] = customer.id
        data["advisor_id"] = folio.advisor_id

        try:
            transaction = await self.transactions.create(data)
            if transaction.transaction_status == TransactionStatus.COMPLETED:
                await self._apply_completed_transaction(transaction)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("Transaction could not be created") from exc

        await self.db.refresh(transaction)
        return transaction

    async def list_transactions(
        self,
        current_user: User,
        *,
        limit: int = 50,
        offset: int = 0,
        customer_id: UUID | None = None,
        scheme_id: UUID | None = None,
        transaction_type: TransactionType | None = None,
        transaction_status: TransactionStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[InvestmentTransaction]:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        if customer_id is not None:
            await self._assert_can_read_customer(current_user, customer_id)
        return await self.transactions.list_by_advisor(
            advisor_id,
            limit=limit,
            offset=offset,
            customer_id=customer_id,
            scheme_id=scheme_id,
            transaction_type=transaction_type,
            transaction_status=transaction_status,
            date_from=date_from,
            date_to=date_to,
        )

    async def get_transaction(self, current_user: User, transaction_id: UUID) -> InvestmentTransaction:
        transaction = await self.transactions.get_by_id(transaction_id)
        if transaction is None:
            raise NotFoundException("Transaction not found")
        await self._assert_can_read_transaction(current_user, transaction)
        return transaction

    async def update_transaction(
        self,
        current_user: User,
        transaction_id: UUID,
        payload: TransactionUpdate,
    ) -> InvestmentTransaction:
        self._assert_can_mutate(current_user)
        transaction = await self.get_transaction(current_user, transaction_id)
        update_data = payload.model_dump(exclude_unset=True)

        old_status = transaction.transaction_status
        updated = await self.transactions.update(transaction, update_data)
        if old_status != TransactionStatus.COMPLETED and updated.transaction_status == TransactionStatus.COMPLETED:
            if updated.transaction_type in OUTFLOW_TYPES:
                available_units = await self._available_units(
                    customer_id=updated.customer_id,
                    folio_id=updated.folio_id,
                    scheme_id=updated.scheme_id,
                )
                if updated.units > available_units:
                    raise BadRequestException("Transaction units exceed available holding units")
            await self._apply_completed_transaction(updated)
        await self.db.commit()
        await self.db.refresh(updated)
        return updated

    async def delete_transaction(self, current_user: User, transaction_id: UUID) -> None:
        self._assert_can_mutate(current_user)
        transaction = await self.get_transaction(current_user, transaction_id)
        await self.transactions.soft_delete(transaction)
        await self.db.commit()

    async def customer_transaction_summary(
        self,
        current_user: User,
        customer_id: UUID,
    ) -> CustomerTransactionSummary:
        await self._assert_can_read_customer(current_user, customer_id)
        summary = await self.transactions.customer_transaction_summary(customer_id)
        return CustomerTransactionSummary(customer_id=customer_id, **summary)

    async def _validate_transaction_relationships(
        self,
        current_user: User,
        payload: TransactionCreate,
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
            raise BadRequestException("Transaction customer_id must match folio customer_id")
        if folio.advisor_id != customer.advisor_id:
            raise BadRequestException("Folio advisor_id must match customer advisor ownership")
        if payload.advisor_id is not None and payload.advisor_id != folio.advisor_id:
            raise BadRequestException("Transaction advisor_id must match folio advisor_id")

        if payload.transaction_type == TransactionType.SIP_INSTALLMENT:
            if payload.sip_id is None:
                raise BadRequestException("SIP installment transactions require sip_id")
            sip = await self.sips.get_by_id(payload.sip_id)
            if sip is None:
                raise NotFoundException("SIP not found")
            if (
                sip.customer_id != customer.id
                or sip.advisor_id != folio.advisor_id
                or sip.folio_id != folio.id
                or sip.scheme_id != payload.scheme_id
            ):
                raise BadRequestException("SIP must match transaction customer, advisor, folio, and scheme")

        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            if folio.advisor_id != advisor.id:
                raise NotFoundException("Folio not found")
        return customer, folio

    async def _apply_completed_transaction(self, transaction: InvestmentTransaction) -> PortfolioHolding:
        holding = await self.holdings.get_by_folio_and_scheme(
            folio_id=transaction.folio_id,
            scheme_id=transaction.scheme_id,
        )

        if holding is None:
            if transaction.transaction_type in OUTFLOW_TYPES:
                raise BadRequestException("Holding not found")
            holding = await self.holdings.create(
                {
                    "folio_id": transaction.folio_id,
                    "customer_id": transaction.customer_id,
                    "advisor_id": transaction.advisor_id,
                    "scheme_id": transaction.scheme_id,
                    "invested_amount": Decimal("0"),
                    "current_value": Decimal("0"),
                    "units": Decimal("0"),
                    "average_nav": transaction.nav,
                    "current_nav": transaction.nav,
                    "valuation_date": transaction.transaction_date.date(),
                }
            )

        if transaction.transaction_type in INFLOW_TYPES:
            total_cost = Decimal(holding.invested_amount or 0) + transaction.amount
            total_units = Decimal(holding.units or 0) + transaction.units
            holding.units = total_units
            holding.invested_amount = total_cost
            holding.current_value = Decimal(holding.current_value or 0) + transaction.amount
            holding.average_nav = total_cost / total_units if total_units else transaction.nav
            holding.current_nav = transaction.nav
            holding.valuation_date = transaction.transaction_date.date()
        elif transaction.transaction_type in OUTFLOW_TYPES:
            existing_units = Decimal(holding.units or 0)
            if transaction.units > existing_units:
                raise BadRequestException("Transaction units exceed available holding units")
            ratio = transaction.units / existing_units if existing_units else Decimal("0")
            holding.units = existing_units - transaction.units
            holding.current_value = max(Decimal("0"), Decimal(holding.current_value or 0) - (Decimal(holding.current_value or 0) * ratio))
            holding.invested_amount = max(
                Decimal("0"),
                Decimal(holding.invested_amount or 0) - (Decimal(holding.invested_amount or 0) * ratio),
            )
            holding.current_nav = transaction.nav
            holding.valuation_date = transaction.transaction_date.date()

        await self.db.flush()
        return holding

    async def _available_units(self, *, customer_id: UUID, folio_id: UUID, scheme_id: UUID) -> Decimal:
        holding = await self.holdings.get_by_folio_and_scheme(folio_id=folio_id, scheme_id=scheme_id)
        if holding is not None and holding.customer_id == customer_id:
            return Decimal(holding.units or 0)
        return await self.transactions.calculate_scheme_units_for_customer(customer_id=customer_id, scheme_id=scheme_id)

    def _assert_can_mutate(self, current_user: User) -> None:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")

    async def _resolve_read_advisor_id(self, current_user: User) -> UUID | None:
        if current_user.role in {UserRole.SUPER_ADMIN, UserRole.COMPLIANCE}:
            return None
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            return advisor.id
        raise ForbiddenException("Insufficient permissions")

    async def _assert_can_read_transaction(self, current_user: User, transaction: InvestmentTransaction) -> None:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        if advisor_id is not None and transaction.advisor_id != advisor_id:
            raise NotFoundException("Transaction not found")

    async def _assert_can_read_customer(self, current_user: User, customer_id: UUID) -> None:
        customer = await self.customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundException("Customer not found")
        advisor_id = await self._resolve_read_advisor_id(current_user)
        if advisor_id is not None and customer.advisor_id != advisor_id:
            raise NotFoundException("Customer not found")
