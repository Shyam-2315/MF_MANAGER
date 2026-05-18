from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.main import app
from app.models.transaction import InvestmentTransaction, TransactionStatus, TransactionType
from app.models.user import UserRole
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate
from app.services.advisor_service import AdvisorService
from app.services.transaction_service import InvestmentTransactionService


def make_user(role: UserRole = UserRole.ADVISOR, user_id: UUID | None = None):
    return SimpleNamespace(id=user_id or uuid4(), role=role, is_active=True)


def make_advisor(advisor_id: UUID | None = None, user_id: UUID | None = None):
    return SimpleNamespace(id=advisor_id or uuid4(), user_id=user_id or uuid4())


def make_customer(customer_id: UUID | None = None, advisor_id: UUID | None = None, is_active: bool = True):
    return SimpleNamespace(id=customer_id or uuid4(), advisor_id=advisor_id or uuid4(), is_active=is_active)


def make_folio(folio_id: UUID | None = None, customer_id: UUID | None = None, advisor_id: UUID | None = None):
    return SimpleNamespace(id=folio_id or uuid4(), customer_id=customer_id or uuid4(), advisor_id=advisor_id or uuid4(), is_active=True)


def make_scheme(scheme_id: UUID | None = None):
    return SimpleNamespace(id=scheme_id or uuid4(), is_active=True)


def make_sip(customer_id: UUID, advisor_id: UUID, folio_id: UUID, scheme_id: UUID):
    return SimpleNamespace(id=uuid4(), customer_id=customer_id, advisor_id=advisor_id, folio_id=folio_id, scheme_id=scheme_id, is_active=True)


def make_holding(
    *,
    folio_id: UUID,
    customer_id: UUID,
    advisor_id: UUID,
    scheme_id: UUID,
    invested_amount: Decimal = Decimal("10000"),
    current_value: Decimal = Decimal("10000"),
    units: Decimal = Decimal("100"),
):
    return SimpleNamespace(
        id=uuid4(),
        folio_id=folio_id,
        customer_id=customer_id,
        advisor_id=advisor_id,
        scheme_id=scheme_id,
        invested_amount=invested_amount,
        current_value=current_value,
        units=units,
        average_nav=Decimal("100"),
        current_nav=Decimal("100"),
        valuation_date=datetime.now(UTC).date(),
        is_active=True,
    )


def transaction_payload(customer_id: UUID, folio_id: UUID, scheme_id: UUID, **overrides) -> TransactionCreate:
    payload = {
        "customer_id": customer_id,
        "folio_id": folio_id,
        "scheme_id": scheme_id,
        "transaction_type": TransactionType.BUY,
        "transaction_status": TransactionStatus.COMPLETED,
        "amount": Decimal("10000"),
        "units": Decimal("100"),
        "nav": Decimal("100"),
        "transaction_date": datetime(2026, 5, 18, tzinfo=UTC),
    }
    payload.update(overrides)
    return TransactionCreate(**payload)


def make_transaction(**overrides):
    now = datetime.now(UTC)
    payload = {
        "id": uuid4(),
        "customer_id": uuid4(),
        "advisor_id": uuid4(),
        "folio_id": uuid4(),
        "scheme_id": uuid4(),
        "sip_id": None,
        "transaction_type": TransactionType.BUY,
        "transaction_status": TransactionStatus.COMPLETED,
        "amount": Decimal("10000"),
        "units": Decimal("100"),
        "nav": Decimal("100"),
        "transaction_date": datetime(2026, 5, 18, tzinfo=UTC),
        "settlement_date": None,
        "external_reference": None,
        "notes": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


class FakeDb:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, _entity) -> None:
        return None

    async def flush(self) -> None:
        return None


class FakeAdvisorRepository:
    def __init__(self, advisor_by_user_id=None) -> None:
        self.advisor_by_user_id = advisor_by_user_id or {}

    async def get_by_user_id(self, user_id):
        return self.advisor_by_user_id.get(user_id)


class FakeCustomerRepository:
    def __init__(self, customers=None) -> None:
        self.customers = list(customers or [])

    async def get_by_id(self, customer_id, *, active_only=True):
        return next((c for c in self.customers if c.id == customer_id and (not active_only or c.is_active)), None)


class FakeFolioRepository:
    def __init__(self, folios=None) -> None:
        self.folios = list(folios or [])

    async def get_by_id(self, folio_id, *, active_only=True):
        return next((f for f in self.folios if f.id == folio_id and active_only), None)


class FakeSchemeRepository:
    def __init__(self, schemes=None) -> None:
        self.schemes = list(schemes or [])

    async def get_by_id(self, scheme_id, *, active_only=True):
        return next((s for s in self.schemes if s.id == scheme_id and (not active_only or s.is_active)), None)


class FakeSIPRepository:
    def __init__(self, sips=None) -> None:
        self.sips = list(sips or [])

    async def get_by_id(self, sip_id, *, active_only=True):
        return next((s for s in self.sips if s.id == sip_id and (not active_only or s.is_active)), None)


class FakeHoldingRepository:
    def __init__(self, holdings=None) -> None:
        self.holdings = list(holdings or [])

    async def create(self, data):
        holding = make_holding(
            folio_id=data["folio_id"],
            customer_id=data["customer_id"],
            advisor_id=data["advisor_id"],
            scheme_id=data["scheme_id"],
            invested_amount=data["invested_amount"],
            current_value=data["current_value"],
            units=data["units"],
        )
        holding.average_nav = data["average_nav"]
        holding.current_nav = data["current_nav"]
        self.holdings.append(holding)
        return holding

    async def get_by_folio_and_scheme(self, *, folio_id, scheme_id, active_only=True):
        return next((h for h in self.holdings if h.folio_id == folio_id and h.scheme_id == scheme_id and (not active_only or h.is_active)), None)


class FakeTransactionRepository:
    def __init__(self, transactions=None) -> None:
        self.transactions = list(transactions or [])
        self.last_filters = None

    async def create(self, data):
        transaction = make_transaction(**data)
        self.transactions.append(transaction)
        return transaction

    async def get_by_id(self, transaction_id, *, active_only=True):
        return next((t for t in self.transactions if t.id == transaction_id and (not active_only or t.is_active)), None)

    async def list_by_advisor(self, advisor_id=None, **filters):
        self.last_filters = {"advisor_id": advisor_id, **filters}
        rows = [t for t in self.transactions if t.is_active and (advisor_id is None or t.advisor_id == advisor_id)]
        if filters.get("customer_id") is not None:
            rows = [t for t in rows if t.customer_id == filters["customer_id"]]
        if filters.get("scheme_id") is not None:
            rows = [t for t in rows if t.scheme_id == filters["scheme_id"]]
        if filters.get("transaction_type") is not None:
            rows = [t for t in rows if t.transaction_type == filters["transaction_type"]]
        if filters.get("transaction_status") is not None:
            rows = [t for t in rows if t.transaction_status == filters["transaction_status"]]
        return rows

    async def update(self, transaction, data):
        for field, value in data.items():
            setattr(transaction, field, value)
        return transaction

    async def soft_delete(self, transaction):
        transaction.is_active = False
        return transaction

    async def calculate_scheme_units_for_customer(self, *, customer_id, scheme_id):
        units = Decimal("0")
        for transaction in self.transactions:
            if transaction.customer_id != customer_id or transaction.scheme_id != scheme_id:
                continue
            if not transaction.is_active or transaction.transaction_status != TransactionStatus.COMPLETED:
                continue
            if transaction.transaction_type in {TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN}:
                units += transaction.units
            elif transaction.transaction_type in {TransactionType.SELL, TransactionType.SWITCH_OUT}:
                units -= transaction.units
        return units

    async def customer_transaction_summary(self, customer_id):
        rows = [
            t
            for t in self.transactions
            if t.customer_id == customer_id and t.is_active and t.transaction_status == TransactionStatus.COMPLETED
        ]
        return {
            "total_transactions": len(rows),
            "total_invested_amount": sum((t.amount for t in rows if t.transaction_type in {TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN}), Decimal("0")),
            "total_sell_amount": sum((t.amount for t in rows if t.transaction_type in {TransactionType.SELL, TransactionType.SWITCH_OUT}), Decimal("0")),
            "total_units": sum(
                (
                    t.units if t.transaction_type in {TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN} else -t.units
                    for t in rows
                    if t.transaction_type != TransactionType.DIVIDEND
                ),
                Decimal("0"),
            ),
            "latest_transaction_date": max((t.transaction_date for t in rows), default=None),
        }


def make_transaction_service(
    *,
    advisor_repo=None,
    customer_repo=None,
    folio_repo=None,
    scheme_repo=None,
    sip_repo=None,
    holding_repo=None,
    transaction_repo=None,
) -> InvestmentTransactionService:
    service = InvestmentTransactionService(FakeDb())
    service.advisors = advisor_repo or FakeAdvisorRepository()
    service.customers = customer_repo or FakeCustomerRepository()
    service.folios = folio_repo or FakeFolioRepository()
    service.schemes = scheme_repo or FakeSchemeRepository()
    service.sips = sip_repo or FakeSIPRepository()
    service.holdings = holding_repo or FakeHoldingRepository()
    service.transactions = transaction_repo or FakeTransactionRepository()
    return service


def setup_owned_context():
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    customer = make_customer(advisor_id=advisor.id)
    folio = make_folio(customer_id=customer.id, advisor_id=advisor.id)
    scheme = make_scheme()
    return advisor_user, advisor, customer, folio, scheme


def test_transaction_model_and_swagger_routes_are_registered() -> None:
    assert InvestmentTransaction.__table__.c.amount.nullable is False
    assert TransactionType.SIP_INSTALLMENT.value == "SIP_INSTALLMENT"
    assert TransactionStatus.COMPLETED.value == "COMPLETED"

    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/transactions" in schema["paths"]
    assert "/api/transactions/{transaction_id}" in schema["paths"]
    assert "/api/customers/{customer_id}/transaction-summary" in schema["paths"]


@pytest.mark.anyio
async def test_buy_transaction_creates_holding() -> None:
    advisor_user, advisor, customer, folio, scheme = setup_owned_context()
    holdings = FakeHoldingRepository()
    service = make_transaction_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        folio_repo=FakeFolioRepository([folio]),
        scheme_repo=FakeSchemeRepository([scheme]),
        holding_repo=holdings,
    )

    transaction = await service.create_transaction(advisor_user, transaction_payload(customer.id, folio.id, scheme.id))

    assert transaction.advisor_id == advisor.id
    assert len(holdings.holdings) == 1
    assert holdings.holdings[0].units == Decimal("100")
    assert holdings.holdings[0].invested_amount == Decimal("10000")


@pytest.mark.anyio
async def test_sip_installment_updates_holding() -> None:
    advisor_user, advisor, customer, folio, scheme = setup_owned_context()
    holding = make_holding(folio_id=folio.id, customer_id=customer.id, advisor_id=advisor.id, scheme_id=scheme.id)
    sip = make_sip(customer.id, advisor.id, folio.id, scheme.id)
    service = make_transaction_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        folio_repo=FakeFolioRepository([folio]),
        scheme_repo=FakeSchemeRepository([scheme]),
        sip_repo=FakeSIPRepository([sip]),
        holding_repo=FakeHoldingRepository([holding]),
    )

    await service.create_transaction(
        advisor_user,
        transaction_payload(
            customer.id,
            folio.id,
            scheme.id,
            sip_id=sip.id,
            transaction_type=TransactionType.SIP_INSTALLMENT,
            amount=Decimal("2000"),
            units=Decimal("20"),
        ),
    )

    assert holding.units == Decimal("120")
    assert holding.invested_amount == Decimal("12000")


@pytest.mark.anyio
async def test_sell_transaction_reduces_units_and_exceeding_units_rejected() -> None:
    advisor_user, advisor, customer, folio, scheme = setup_owned_context()
    holding = make_holding(folio_id=folio.id, customer_id=customer.id, advisor_id=advisor.id, scheme_id=scheme.id)
    service = make_transaction_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        folio_repo=FakeFolioRepository([folio]),
        scheme_repo=FakeSchemeRepository([scheme]),
        holding_repo=FakeHoldingRepository([holding]),
    )

    await service.create_transaction(
        advisor_user,
        transaction_payload(
            customer.id,
            folio.id,
            scheme.id,
            transaction_type=TransactionType.SELL,
            amount=Decimal("2500"),
            units=Decimal("25"),
        ),
    )
    assert holding.units == Decimal("75")
    assert holding.current_value == Decimal("7500.00")

    with pytest.raises(BadRequestException):
        await service.create_transaction(
            advisor_user,
            transaction_payload(
                customer.id,
                folio.id,
                scheme.id,
                transaction_type=TransactionType.SELL,
                amount=Decimal("10000"),
                units=Decimal("100"),
            ),
        )


@pytest.mark.anyio
async def test_failed_transaction_does_not_affect_holdings() -> None:
    advisor_user, advisor, customer, folio, scheme = setup_owned_context()
    holdings = FakeHoldingRepository()
    service = make_transaction_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        folio_repo=FakeFolioRepository([folio]),
        scheme_repo=FakeSchemeRepository([scheme]),
        holding_repo=holdings,
    )

    await service.create_transaction(
        advisor_user,
        transaction_payload(customer.id, folio.id, scheme.id, transaction_status=TransactionStatus.FAILED),
    )

    assert holdings.holdings == []


@pytest.mark.anyio
async def test_advisor_cannot_create_transaction_for_another_advisor_customer() -> None:
    advisor_user, advisor, customer, folio, scheme = setup_owned_context()
    other_advisor_id = uuid4()
    customer.advisor_id = other_advisor_id
    folio.advisor_id = other_advisor_id
    service = make_transaction_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        folio_repo=FakeFolioRepository([folio]),
        scheme_repo=FakeSchemeRepository([scheme]),
    )

    with pytest.raises(NotFoundException):
        await service.create_transaction(advisor_user, transaction_payload(customer.id, folio.id, scheme.id))


@pytest.mark.anyio
async def test_compliance_read_only_and_customer_blocked() -> None:
    transaction = make_transaction()
    customer = make_customer(customer_id=transaction.customer_id, advisor_id=transaction.advisor_id)
    service = make_transaction_service(
        customer_repo=FakeCustomerRepository([customer]),
        transaction_repo=FakeTransactionRepository([transaction]),
    )

    assert await service.get_transaction(make_user(UserRole.COMPLIANCE), transaction.id) == transaction
    assert await service.list_transactions(make_user(UserRole.COMPLIANCE)) == [transaction]

    with pytest.raises(ForbiddenException):
        await service.update_transaction(make_user(UserRole.COMPLIANCE), transaction.id, TransactionUpdate(notes="No"))
    with pytest.raises(ForbiddenException):
        await service.delete_transaction(make_user(UserRole.COMPLIANCE), transaction.id)
    with pytest.raises(ForbiddenException):
        await service.list_transactions(make_user(UserRole.CUSTOMER))


@pytest.mark.anyio
async def test_filters_work_and_soft_delete_hides_transaction() -> None:
    advisor_user, advisor, customer, _folio, scheme = setup_owned_context()
    transaction = make_transaction(customer_id=customer.id, advisor_id=advisor.id, scheme_id=scheme.id)
    repo = FakeTransactionRepository([transaction])
    service = make_transaction_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        transaction_repo=repo,
    )

    rows = await service.list_transactions(
        advisor_user,
        customer_id=customer.id,
        scheme_id=scheme.id,
        transaction_type=TransactionType.BUY,
        transaction_status=TransactionStatus.COMPLETED,
    )
    assert rows == [transaction]
    assert repo.last_filters["customer_id"] == customer.id

    await service.delete_transaction(advisor_user, transaction.id)
    assert await service.list_transactions(advisor_user) == []


@pytest.mark.anyio
async def test_transaction_summary_calculates_correctly() -> None:
    customer = make_customer()
    transactions = [
        make_transaction(customer_id=customer.id, transaction_type=TransactionType.BUY, amount=Decimal("10000"), units=Decimal("100")),
        make_transaction(customer_id=customer.id, transaction_type=TransactionType.SELL, amount=Decimal("2500"), units=Decimal("25")),
        make_transaction(customer_id=customer.id, transaction_status=TransactionStatus.FAILED, amount=Decimal("999"), units=Decimal("9")),
    ]
    service = make_transaction_service(
        customer_repo=FakeCustomerRepository([customer]),
        transaction_repo=FakeTransactionRepository(transactions),
    )

    summary = await service.customer_transaction_summary(make_user(UserRole.SUPER_ADMIN), customer.id)

    assert summary.total_transactions == 2
    assert summary.total_invested_amount == Decimal("10000")
    assert summary.total_sell_amount == Decimal("2500")
    assert summary.total_units == Decimal("75")
    assert summary.latest_transaction_date == datetime(2026, 5, 18, tzinfo=UTC)


@pytest.mark.anyio
async def test_recent_dashboard_transactions_work() -> None:
    class FakeAdvisorDashboardRepository:
        async def get_by_user_id(self, user_id):
            return make_advisor(user_id=user_id)

        async def list_recent_transactions(self, _advisor_id):
            return [
                {
                    "id": uuid4(),
                    "customer_id": uuid4(),
                    "transaction_type": "BUY",
                    "amount": Decimal("10000"),
                    "status": "COMPLETED",
                    "transaction_date": datetime(2026, 5, 18, tzinfo=UTC),
                }
            ]

        async def count_customers(self, _advisor_id):
            return 1

        async def sum_total_aum(self, _advisor_id):
            return Decimal("10000")

        async def sum_monthly_sip_amount(self, _advisor_id):
            return Decimal("2500")

        async def count_pending_kyc_customers(self, _advisor_id):
            return 0

        async def count_active_sips(self, _advisor_id):
            return 1

    service = AdvisorService(FakeDb())
    service.advisors = FakeAdvisorDashboardRepository()

    summary = await service.dashboard_summary(make_user(UserRole.ADVISOR))

    assert len(summary.recent_transactions) == 1
    assert summary.recent_transactions[0].transaction_type == "BUY"
    assert summary.recent_transactions[0].status == "COMPLETED"


def test_transaction_routes_delegate_to_services(monkeypatch: pytest.MonkeyPatch) -> None:
    current_user = make_user(UserRole.SUPER_ADMIN)
    transaction = TransactionRead(
        id=uuid4(),
        customer_id=uuid4(),
        advisor_id=uuid4(),
        folio_id=uuid4(),
        scheme_id=uuid4(),
        sip_id=None,
        transaction_type=TransactionType.BUY,
        transaction_status=TransactionStatus.COMPLETED,
        amount=Decimal("10000"),
        units=Decimal("100"),
        nav=Decimal("100"),
        transaction_date=datetime(2026, 5, 18, tzinfo=UTC),
        settlement_date=None,
        external_reference=None,
        notes=None,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeTransactionService:
        def __init__(self, _db) -> None:
            pass

        async def create_transaction(self, _user, _payload):
            return transaction

        async def list_transactions(self, _user, **_filters):
            return [transaction]

        async def get_transaction(self, _user, _transaction_id):
            return transaction

        async def update_transaction(self, _user, _transaction_id, payload):
            return transaction.model_copy(update=payload.model_dump(exclude_unset=True))

        async def delete_transaction(self, _user, _transaction_id):
            return None

        async def customer_transaction_summary(self, _user, customer_id):
            return {
                "customer_id": customer_id,
                "total_transactions": 1,
                "total_invested_amount": Decimal("10000"),
                "total_sell_amount": Decimal("0"),
                "total_units": Decimal("100"),
                "latest_transaction_date": datetime(2026, 5, 18, tzinfo=UTC),
            }

    async def fake_current_user():
        return current_user

    monkeypatch.setattr("app.routes.transactions.InvestmentTransactionService", FakeTransactionService)
    app.dependency_overrides[get_current_user] = fake_current_user
    client = TestClient(app)
    payload = {
        "customer_id": str(transaction.customer_id),
        "folio_id": str(transaction.folio_id),
        "scheme_id": str(transaction.scheme_id),
        "transaction_type": "BUY",
        "transaction_status": "COMPLETED",
        "amount": "10000",
        "units": "100",
        "nav": "100",
        "transaction_date": "2026-05-18T00:00:00Z",
    }

    assert client.post("/api/transactions", json=payload).status_code == 201
    assert client.get("/api/transactions?transaction_type=BUY&transaction_status=COMPLETED").status_code == 200
    assert client.get(f"/api/transactions/{transaction.id}").status_code == 200
    assert client.patch(f"/api/transactions/{transaction.id}", json={"notes": "Checked"}).status_code == 200
    assert client.delete(f"/api/transactions/{transaction.id}").status_code == 204
    assert client.get(f"/api/customers/{transaction.customer_id}/transaction-summary").status_code == 200
