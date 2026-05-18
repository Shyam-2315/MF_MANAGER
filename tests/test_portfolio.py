from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.main import app
from app.models.portfolio import Folio, MutualFundScheme, PortfolioHolding
from app.models.user import UserRole
from app.schemas.portfolio import (
    FolioCreate,
    MutualFundSchemeCreate,
    MutualFundSchemeRead,
    MutualFundSchemeUpdate,
    PortfolioHoldingCreate,
)
from app.services.advisor_service import AdvisorService
from app.services.portfolio_service import FolioService, MutualFundSchemeService, PortfolioHoldingService


def make_user(role: UserRole = UserRole.ADVISOR, user_id: UUID | None = None):
    return SimpleNamespace(id=user_id or uuid4(), role=role, is_active=True)


def make_advisor(advisor_id: UUID | None = None, user_id: UUID | None = None):
    return SimpleNamespace(id=advisor_id or uuid4(), user_id=user_id or uuid4())


def make_customer(customer_id: UUID | None = None, advisor_id: UUID | None = None):
    return SimpleNamespace(id=customer_id or uuid4(), advisor_id=advisor_id or uuid4(), is_active=True)


def make_scheme(scheme_id: UUID | None = None, scheme_code: str = "MF001", is_active: bool = True):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=scheme_id or uuid4(),
        scheme_code=scheme_code,
        scheme_name="Bluechip Fund",
        amc_name="AMC",
        category="Equity",
        sub_category="Large Cap",
        risk_level="High",
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def make_folio(
    folio_id: UUID | None = None,
    customer_id: UUID | None = None,
    advisor_id: UUID | None = None,
    folio_number: str = "FOLIO-1",
    is_active: bool = True,
):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=folio_id or uuid4(),
        customer_id=customer_id or uuid4(),
        advisor_id=advisor_id or uuid4(),
        folio_number=folio_number,
        platform="RTA",
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def make_holding(
    holding_id: UUID | None = None,
    folio_id: UUID | None = None,
    customer_id: UUID | None = None,
    advisor_id: UUID | None = None,
    scheme_id: UUID | None = None,
    is_active: bool = True,
):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=holding_id or uuid4(),
        folio_id=folio_id or uuid4(),
        customer_id=customer_id or uuid4(),
        advisor_id=advisor_id or uuid4(),
        scheme_id=scheme_id or uuid4(),
        invested_amount=Decimal("1000"),
        current_value=Decimal("1200"),
        units=Decimal("10"),
        average_nav=Decimal("100"),
        current_nav=Decimal("120"),
        valuation_date=date(2026, 5, 17),
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


class FakeDb:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, _entity) -> None:
        return None


class FakeAdvisorRepository:
    def __init__(self, advisor_by_user_id=None) -> None:
        self.advisor_by_user_id = advisor_by_user_id or {}

    async def get_by_user_id(self, user_id):
        return self.advisor_by_user_id.get(user_id)


class FakeSchemeRepository:
    def __init__(self, schemes=None) -> None:
        self.schemes = list(schemes or [])

    async def create(self, data):
        scheme = make_scheme(scheme_code=data["scheme_code"])
        self.schemes.append(scheme)
        return scheme

    async def get_by_id(self, scheme_id, *, active_only=True):
        return next((s for s in self.schemes if s.id == scheme_id and (not active_only or s.is_active)), None)

    async def get_by_scheme_code(self, scheme_code, *, active_only=True):
        return next((s for s in self.schemes if s.scheme_code == scheme_code and (not active_only or s.is_active)), None)

    async def list(self, **_kwargs):
        return [scheme for scheme in self.schemes if scheme.is_active]

    async def update(self, scheme, data):
        for field, value in data.items():
            setattr(scheme, field, value)
        return scheme

    async def soft_delete(self, scheme):
        scheme.is_active = False
        return scheme


class FakeCustomerRepository:
    def __init__(self, customers=None) -> None:
        self.customers = list(customers or [])

    async def get_by_id(self, customer_id, *, active_only=True):
        return next((c for c in self.customers if c.id == customer_id and (not active_only or c.is_active)), None)


class FakeFolioRepository:
    def __init__(self, folios=None) -> None:
        self.folios = list(folios or [])

    async def create(self, data):
        folio = make_folio(customer_id=data["customer_id"], advisor_id=data["advisor_id"], folio_number=data["folio_number"])
        self.folios.append(folio)
        return folio

    async def get_by_id(self, folio_id, *, active_only=True):
        return next((f for f in self.folios if f.id == folio_id and (not active_only or f.is_active)), None)

    async def get_by_folio_number_for_customer(self, *, customer_id, folio_number, active_only=True):
        return next(
            (
                f
                for f in self.folios
                if f.customer_id == customer_id and f.folio_number == folio_number and (not active_only or f.is_active)
            ),
            None,
        )

    async def list_by_advisor(self, advisor_id=None, **_kwargs):
        return [f for f in self.folios if f.is_active and (advisor_id is None or f.advisor_id == advisor_id)]

    async def update(self, folio, data):
        for field, value in data.items():
            setattr(folio, field, value)
        return folio

    async def soft_delete(self, folio):
        folio.is_active = False
        return folio


class FakeHoldingRepository:
    def __init__(self, holdings=None) -> None:
        self.holdings = list(holdings or [])

    async def create(self, data):
        holding = make_holding(
            folio_id=data["folio_id"],
            customer_id=data["customer_id"],
            advisor_id=data["advisor_id"],
            scheme_id=data["scheme_id"],
        )
        holding.invested_amount = data.get("invested_amount", Decimal("0"))
        holding.current_value = data.get("current_value", Decimal("0"))
        self.holdings.append(holding)
        return holding

    async def get_by_id(self, holding_id, *, active_only=True):
        return next((h for h in self.holdings if h.id == holding_id and (not active_only or h.is_active)), None)

    async def get_by_folio_and_scheme(self, *, folio_id, scheme_id, active_only=True):
        return next(
            (h for h in self.holdings if h.folio_id == folio_id and h.scheme_id == scheme_id and (not active_only or h.is_active)),
            None,
        )

    async def list_by_advisor(self, advisor_id=None, **_kwargs):
        return [h for h in self.holdings if h.is_active and (advisor_id is None or h.advisor_id == advisor_id)]

    async def update(self, holding, data):
        for field, value in data.items():
            setattr(holding, field, value)
        return holding

    async def soft_delete(self, holding):
        holding.is_active = False
        return holding

    async def calculate_customer_portfolio_summary(self, customer_id):
        rows = [h for h in self.holdings if h.customer_id == customer_id and h.is_active]
        invested = sum((h.invested_amount for h in rows), Decimal("0"))
        current = sum((h.current_value for h in rows), Decimal("0"))
        gain_loss = current - invested
        return {
            "total_invested_amount": invested,
            "total_current_value": current,
            "total_gain_loss": gain_loss,
            "total_gain_loss_percentage": gain_loss / invested * Decimal("100") if invested else Decimal("0"),
            "holdings_count": len(rows),
        }


def test_portfolio_models_and_swagger_routes_are_registered() -> None:
    assert MutualFundScheme.__table__.c.scheme_code.unique is True
    assert any(constraint.name == "uq_folios_customer_folio_number" for constraint in Folio.__table__.constraints)
    assert any(index.name == "uq_portfolio_holdings_active_folio_scheme" for index in PortfolioHolding.__table__.indexes)

    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/schemes" in schema["paths"]
    assert "/api/folios" in schema["paths"]
    assert "/api/portfolio-holdings" in schema["paths"]
    assert "/api/customers/{customer_id}/portfolio-summary" in schema["paths"]


@pytest.mark.anyio
async def test_scheme_create_list_update_delete_and_duplicate_rejection() -> None:
    service = MutualFundSchemeService(FakeDb())
    service.schemes = FakeSchemeRepository()
    admin = make_user(UserRole.SUPER_ADMIN)

    scheme = await service.create_scheme(admin, MutualFundSchemeCreate(scheme_code="MF001", scheme_name="Fund", amc_name="AMC"))
    assert await service.list_schemes(admin) == [scheme]

    updated = await service.update_scheme(admin, scheme.id, MutualFundSchemeUpdate(scheme_name="Updated Fund"))
    assert updated.scheme_name == "Updated Fund"

    with pytest.raises(BadRequestException):
        await service.create_scheme(admin, MutualFundSchemeCreate(scheme_code="MF001", scheme_name="Fund", amc_name="AMC"))

    await service.delete_scheme(admin, scheme.id)
    assert await service.list_schemes(admin) == []


@pytest.mark.anyio
async def test_compliance_can_read_schemes_but_not_mutate_and_customer_blocked() -> None:
    service = MutualFundSchemeService(FakeDb())
    scheme = make_scheme()
    service.schemes = FakeSchemeRepository([scheme])

    assert await service.list_schemes(make_user(UserRole.COMPLIANCE)) == [scheme]
    with pytest.raises(ForbiddenException):
        await service.create_scheme(make_user(UserRole.COMPLIANCE), MutualFundSchemeCreate(scheme_code="MF002", scheme_name="Fund", amc_name="AMC"))
    with pytest.raises(ForbiddenException):
        await service.list_schemes(make_user(UserRole.CUSTOMER))


@pytest.mark.anyio
async def test_advisor_can_create_folio_for_own_customer_and_duplicate_is_rejected() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    customer = make_customer(advisor_id=advisor.id)
    service = FolioService(FakeDb())
    service.advisors = FakeAdvisorRepository({advisor_user.id: advisor})
    service.customers = FakeCustomerRepository([customer])
    service.folios = FakeFolioRepository()

    folio = await service.create_folio(advisor_user, FolioCreate(customer_id=customer.id, folio_number="FOLIO-1"))
    assert folio.advisor_id == advisor.id

    with pytest.raises(BadRequestException):
        await service.create_folio(advisor_user, FolioCreate(customer_id=customer.id, folio_number="FOLIO-1"))


@pytest.mark.anyio
async def test_advisor_cannot_create_folio_for_another_advisors_customer() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    service = FolioService(FakeDb())
    service.advisors = FakeAdvisorRepository({advisor_user.id: make_advisor(user_id=advisor_user.id)})
    service.customers = FakeCustomerRepository([make_customer(advisor_id=uuid4())])

    with pytest.raises(NotFoundException):
        await service.create_folio(advisor_user, FolioCreate(customer_id=service.customers.customers[0].id, folio_number="FOLIO-1"))


@pytest.mark.anyio
async def test_advisor_can_create_holding_and_duplicate_active_holding_is_rejected() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    customer = make_customer(advisor_id=advisor.id)
    scheme = make_scheme()
    folio = make_folio(customer_id=customer.id, advisor_id=advisor.id)
    service = PortfolioHoldingService(FakeDb())
    service.advisors = FakeAdvisorRepository({advisor_user.id: advisor})
    service.customers = FakeCustomerRepository([customer])
    service.folios = FakeFolioRepository([folio])
    service.schemes = FakeSchemeRepository([scheme])
    service.holdings = FakeHoldingRepository()

    payload = PortfolioHoldingCreate(folio_id=folio.id, customer_id=customer.id, scheme_id=scheme.id, current_value=Decimal("1200"))
    holding = await service.create_holding(advisor_user, payload)
    assert holding.advisor_id == advisor.id

    with pytest.raises(BadRequestException):
        await service.create_holding(advisor_user, payload)


@pytest.mark.anyio
async def test_advisor_cannot_access_another_advisors_holding() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    holding = make_holding(advisor_id=uuid4())
    service = PortfolioHoldingService(FakeDb())
    service.advisors = FakeAdvisorRepository({advisor_user.id: advisor})
    service.holdings = FakeHoldingRepository([holding])

    with pytest.raises(NotFoundException):
        await service.get_holding(advisor_user, holding.id)


@pytest.mark.anyio
async def test_customer_portfolio_summary_calculates_correctly() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    customer = make_customer(advisor_id=advisor.id)
    holdings = [
        make_holding(customer_id=customer.id, advisor_id=advisor.id),
        make_holding(customer_id=customer.id, advisor_id=advisor.id),
    ]
    service = PortfolioHoldingService(FakeDb())
    service.advisors = FakeAdvisorRepository({advisor_user.id: advisor})
    service.customers = FakeCustomerRepository([customer])
    service.holdings = FakeHoldingRepository(holdings)

    summary = await service.customer_portfolio_summary(advisor_user, customer.id)

    assert summary.total_invested_amount == Decimal("2000")
    assert summary.total_current_value == Decimal("2400")
    assert summary.total_gain_loss == Decimal("400")
    assert summary.total_gain_loss_percentage == Decimal("20.0")
    assert summary.holdings_count == 2


@pytest.mark.anyio
async def test_advisor_dashboard_total_aum_uses_active_portfolio_holdings() -> None:
    class FakeAdvisorRepository:
        async def get_by_user_id(self, user_id):
            return make_advisor(user_id=user_id)

        async def list_recent_transactions(self, _advisor_id):
            return []

        async def count_customers(self, _advisor_id):
            return 1

        async def sum_total_aum(self, _advisor_id):
            return Decimal("2400")

        async def sum_monthly_sip_amount(self, _advisor_id):
            return Decimal("0")

        async def count_pending_kyc_customers(self, _advisor_id):
            return 0

        async def count_active_sips(self, _advisor_id):
            return 0

    service = AdvisorService(FakeDb())
    service.advisors = FakeAdvisorRepository()

    summary = await service.dashboard_summary(make_user(UserRole.ADVISOR))

    assert summary.total_aum == Decimal("2400")
    assert summary.monthly_sip_amount == Decimal("0")
    assert summary.active_sips == 0


def test_portfolio_routes_delegate_to_services(monkeypatch: pytest.MonkeyPatch) -> None:
    current_user = make_user(UserRole.SUPER_ADMIN)
    scheme = MutualFundSchemeRead(
        id=uuid4(),
        scheme_code="MF001",
        scheme_name="Fund",
        amc_name="AMC",
        category=None,
        sub_category=None,
        risk_level=None,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeSchemeService:
        def __init__(self, _db) -> None:
            pass

        async def create_scheme(self, _user, _payload):
            return scheme

        async def list_schemes(self, _user, **_kwargs):
            return [scheme]

        async def get_scheme(self, _user, _scheme_id):
            return scheme

        async def update_scheme(self, _user, _scheme_id, _payload):
            return scheme

        async def delete_scheme(self, _user, _scheme_id):
            return None

    async def fake_current_user():
        return current_user

    monkeypatch.setattr("app.routes.portfolio.MutualFundSchemeService", FakeSchemeService)
    app.dependency_overrides[get_current_user] = fake_current_user
    client = TestClient(app)

    assert client.post("/api/schemes", json={"scheme_code": "MF001", "scheme_name": "Fund", "amc_name": "AMC"}).status_code == 201
    assert client.get("/api/schemes").status_code == 200
    assert client.get(f"/api/schemes/{scheme.id}").status_code == 200
    assert client.patch(f"/api/schemes/{scheme.id}", json={"scheme_name": "Updated"}).status_code == 200
    assert client.delete(f"/api/schemes/{scheme.id}").status_code == 204
