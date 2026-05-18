from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dependencies import get_current_user
from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.main import app
from app.models.sip import SIP, SIPFrequency, SIPStatus
from app.models.user import UserRole
from app.schemas.sip import SIPCreate, SIPRead, SIPUpdate
from app.services.advisor_service import AdvisorService
from app.services.sip_service import SIPService


def make_user(role: UserRole = UserRole.ADVISOR, user_id: UUID | None = None):
    return SimpleNamespace(id=user_id or uuid4(), role=role, is_active=True)


def make_advisor(advisor_id: UUID | None = None, user_id: UUID | None = None):
    return SimpleNamespace(id=advisor_id or uuid4(), user_id=user_id or uuid4())


def make_customer(customer_id: UUID | None = None, advisor_id: UUID | None = None, is_active: bool = True):
    return SimpleNamespace(id=customer_id or uuid4(), advisor_id=advisor_id or uuid4(), is_active=is_active)


def make_folio(
    folio_id: UUID | None = None,
    customer_id: UUID | None = None,
    advisor_id: UUID | None = None,
    is_active: bool = True,
):
    return SimpleNamespace(
        id=folio_id or uuid4(),
        customer_id=customer_id or uuid4(),
        advisor_id=advisor_id or uuid4(),
        is_active=is_active,
    )


def make_scheme(scheme_id: UUID | None = None, is_active: bool = True):
    return SimpleNamespace(id=scheme_id or uuid4(), is_active=is_active)


def make_sip(
    *,
    sip_id: UUID | None = None,
    customer_id: UUID | None = None,
    advisor_id: UUID | None = None,
    folio_id: UUID | None = None,
    scheme_id: UUID | None = None,
    sip_amount: Decimal = Decimal("2500"),
    frequency: SIPFrequency = SIPFrequency.MONTHLY,
    status: SIPStatus = SIPStatus.ACTIVE,
    start_date: date = date(2026, 5, 1),
    end_date: date | None = None,
    next_due_date: date | None = date(2026, 6, 1),
    mandate_reference: str | None = None,
    is_active: bool = True,
):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=sip_id or uuid4(),
        customer_id=customer_id or uuid4(),
        advisor_id=advisor_id or uuid4(),
        folio_id=folio_id or uuid4(),
        scheme_id=scheme_id or uuid4(),
        sip_amount=sip_amount,
        frequency=frequency,
        status=status,
        start_date=start_date,
        end_date=end_date,
        next_due_date=next_due_date,
        mandate_reference=mandate_reference,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def sip_payload(customer_id: UUID, folio_id: UUID, scheme_id: UUID, **overrides):
    payload = {
        "customer_id": customer_id,
        "folio_id": folio_id,
        "scheme_id": scheme_id,
        "sip_amount": Decimal("2500"),
        "frequency": SIPFrequency.MONTHLY,
        "status": SIPStatus.ACTIVE,
        "start_date": date(2026, 5, 1),
        "next_due_date": date(2026, 6, 1),
    }
    payload.update(overrides)
    return SIPCreate(**payload)


class FakeDb:
    async def commit(self) -> None:
        return None

    async def refresh(self, _entity) -> None:
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
        return next((f for f in self.folios if f.id == folio_id and (not active_only or f.is_active)), None)


class FakeSchemeRepository:
    def __init__(self, schemes=None) -> None:
        self.schemes = list(schemes or [])

    async def get_by_id(self, scheme_id, *, active_only=True):
        return next((s for s in self.schemes if s.id == scheme_id and (not active_only or s.is_active)), None)


class FakeSIPRepository:
    def __init__(self, sips=None) -> None:
        self.sips = list(sips or [])

    async def create(self, data):
        sip = make_sip(**data)
        self.sips.append(sip)
        return sip

    async def get_by_id(self, sip_id, *, active_only=True):
        return next((s for s in self.sips if s.id == sip_id and (not active_only or s.is_active)), None)

    async def list_by_advisor(self, advisor_id=None, **filters):
        rows = [sip for sip in self.sips if sip.is_active and (advisor_id is None or sip.advisor_id == advisor_id)]
        if filters.get("customer_id") is not None:
            rows = [sip for sip in rows if sip.customer_id == filters["customer_id"]]
        if filters.get("status") is not None:
            rows = [sip for sip in rows if sip.status == filters["status"]]
        if filters.get("frequency") is not None:
            rows = [sip for sip in rows if sip.frequency == filters["frequency"]]
        if filters.get("next_due_before") is not None:
            rows = [sip for sip in rows if sip.next_due_date is not None and sip.next_due_date <= filters["next_due_before"]]
        return rows

    async def update(self, sip, data):
        for field, value in data.items():
            setattr(sip, field, value)
        return sip

    async def soft_delete(self, sip):
        sip.is_active = False
        return sip

    async def customer_sip_summary(self, customer_id):
        rows = [sip for sip in self.sips if sip.customer_id == customer_id and sip.is_active]
        return {
            "active_sips": len([sip for sip in rows if sip.status == SIPStatus.ACTIVE]),
            "paused_sips": len([sip for sip in rows if sip.status == SIPStatus.PAUSED]),
            "cancelled_sips": len([sip for sip in rows if sip.status == SIPStatus.CANCELLED]),
            "completed_sips": len([sip for sip in rows if sip.status == SIPStatus.COMPLETED]),
            "total_monthly_sip_amount": sum(
                (sip.sip_amount for sip in rows if sip.status == SIPStatus.ACTIVE and sip.frequency == SIPFrequency.MONTHLY),
                Decimal("0"),
            ),
            "next_due_sip_date": min(
                (sip.next_due_date for sip in rows if sip.status == SIPStatus.ACTIVE and sip.next_due_date is not None),
                default=None,
            ),
        }


def make_sip_service(*, advisor_repo=None, customer_repo=None, folio_repo=None, scheme_repo=None, sip_repo=None) -> SIPService:
    service = SIPService(FakeDb())
    service.advisors = advisor_repo or FakeAdvisorRepository()
    service.customers = customer_repo or FakeCustomerRepository()
    service.folios = folio_repo or FakeFolioRepository()
    service.schemes = scheme_repo or FakeSchemeRepository()
    service.sips = sip_repo or FakeSIPRepository()
    return service


def test_sip_model_and_swagger_routes_are_registered() -> None:
    assert SIP.__table__.c.sip_amount.nullable is False
    assert SIPFrequency.MONTHLY.value == "MONTHLY"
    assert SIPStatus.CANCELLED.value == "CANCELLED"

    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/sips" in schema["paths"]
    assert "/api/sips/{sip_id}" in schema["paths"]
    assert "/api/customers/{customer_id}/sip-summary" in schema["paths"]


@pytest.mark.anyio
async def test_advisor_can_create_sip_for_own_customer_folio_scheme() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    customer = make_customer(advisor_id=advisor.id)
    folio = make_folio(customer_id=customer.id, advisor_id=advisor.id)
    scheme = make_scheme()
    service = make_sip_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        folio_repo=FakeFolioRepository([folio]),
        scheme_repo=FakeSchemeRepository([scheme]),
    )

    sip = await service.create_sip(advisor_user, sip_payload(customer.id, folio.id, scheme.id))

    assert sip.customer_id == customer.id
    assert sip.advisor_id == advisor.id
    assert sip.sip_amount == Decimal("2500")


@pytest.mark.anyio
async def test_advisor_cannot_create_sip_for_another_advisors_customer() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    other_advisor_id = uuid4()
    customer = make_customer(advisor_id=other_advisor_id)
    folio = make_folio(customer_id=customer.id, advisor_id=other_advisor_id)
    scheme = make_scheme()
    service = make_sip_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        folio_repo=FakeFolioRepository([folio]),
        scheme_repo=FakeSchemeRepository([scheme]),
    )

    with pytest.raises(NotFoundException):
        await service.create_sip(advisor_user, sip_payload(customer.id, folio.id, scheme.id))


@pytest.mark.anyio
async def test_advisor_cannot_create_sip_with_mismatched_folio_customer() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    customer = make_customer(advisor_id=advisor.id)
    folio = make_folio(customer_id=uuid4(), advisor_id=advisor.id)
    scheme = make_scheme()
    service = make_sip_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
        folio_repo=FakeFolioRepository([folio]),
        scheme_repo=FakeSchemeRepository([scheme]),
    )

    with pytest.raises(BadRequestException):
        await service.create_sip(advisor_user, sip_payload(customer.id, folio.id, scheme.id))


def test_sip_schema_rejects_invalid_amount_and_dates() -> None:
    customer_id = uuid4()
    folio_id = uuid4()
    scheme_id = uuid4()

    with pytest.raises(ValidationError):
        sip_payload(customer_id, folio_id, scheme_id, sip_amount=Decimal("0"))
    with pytest.raises(ValidationError):
        sip_payload(customer_id, folio_id, scheme_id, end_date=date(2026, 4, 30))


@pytest.mark.anyio
async def test_compliance_can_read_list_but_cannot_mutate_and_customer_blocked() -> None:
    sip = make_sip()
    customer = make_customer(customer_id=sip.customer_id, advisor_id=sip.advisor_id)
    service = make_sip_service(customer_repo=FakeCustomerRepository([customer]), sip_repo=FakeSIPRepository([sip]))

    assert await service.get_sip(make_user(UserRole.COMPLIANCE), sip.id) == sip
    assert await service.list_sips(make_user(UserRole.COMPLIANCE)) == [sip]

    with pytest.raises(ForbiddenException):
        await service.create_sip(make_user(UserRole.COMPLIANCE), sip_payload(sip.customer_id, sip.folio_id, sip.scheme_id))
    with pytest.raises(ForbiddenException):
        await service.update_sip(make_user(UserRole.COMPLIANCE), sip.id, SIPUpdate(status=SIPStatus.PAUSED))
    with pytest.raises(ForbiddenException):
        await service.delete_sip(make_user(UserRole.COMPLIANCE), sip.id)
    with pytest.raises(ForbiddenException):
        await service.list_sips(make_user(UserRole.CUSTOMER))


@pytest.mark.anyio
async def test_advisor_can_list_only_own_sips() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    own_sip = make_sip(advisor_id=advisor.id)
    other_sip = make_sip(advisor_id=uuid4())
    service = make_sip_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        sip_repo=FakeSIPRepository([own_sip, other_sip]),
    )

    assert await service.list_sips(advisor_user) == [own_sip]


@pytest.mark.anyio
async def test_update_sip_status_and_soft_delete_hides_from_list() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    sip = make_sip(advisor_id=advisor.id)
    service = make_sip_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        sip_repo=FakeSIPRepository([sip]),
    )

    paused = await service.update_sip(advisor_user, sip.id, SIPUpdate(status=SIPStatus.PAUSED))
    assert paused.status == SIPStatus.PAUSED
    cancelled = await service.update_sip(advisor_user, sip.id, SIPUpdate(status=SIPStatus.CANCELLED))
    assert cancelled.status == SIPStatus.CANCELLED

    await service.delete_sip(advisor_user, sip.id)
    assert await service.list_sips(advisor_user) == []


@pytest.mark.anyio
async def test_update_sip_rejects_end_date_before_start_date() -> None:
    sip = make_sip()
    service = make_sip_service(sip_repo=FakeSIPRepository([sip]))

    with pytest.raises(BadRequestException):
        await service.update_sip(make_user(UserRole.SUPER_ADMIN), sip.id, SIPUpdate(end_date=date(2026, 4, 30)))


@pytest.mark.anyio
async def test_customer_sip_summary_calculates_correctly() -> None:
    customer = make_customer()
    sips = [
        make_sip(customer_id=customer.id, advisor_id=customer.advisor_id, sip_amount=Decimal("1000")),
        make_sip(customer_id=customer.id, advisor_id=customer.advisor_id, sip_amount=Decimal("2000"), status=SIPStatus.PAUSED),
        make_sip(customer_id=customer.id, advisor_id=customer.advisor_id, status=SIPStatus.CANCELLED),
        make_sip(customer_id=customer.id, advisor_id=customer.advisor_id, status=SIPStatus.COMPLETED),
    ]
    service = make_sip_service(customer_repo=FakeCustomerRepository([customer]), sip_repo=FakeSIPRepository(sips))

    summary = await service.customer_sip_summary(make_user(UserRole.SUPER_ADMIN), customer.id)

    assert summary.active_sips == 1
    assert summary.paused_sips == 1
    assert summary.cancelled_sips == 1
    assert summary.completed_sips == 1
    assert summary.total_monthly_sip_amount == Decimal("1000")
    assert summary.next_due_sip_date == date(2026, 6, 1)


@pytest.mark.anyio
async def test_advisor_dashboard_sip_fields_use_real_values() -> None:
    advisor_id = uuid4()
    advisor_user = make_user(UserRole.ADVISOR)

    class FakeAdvisorDashboardRepository:
        async def get_by_user_id(self, user_id):
            return make_advisor(advisor_id=advisor_id, user_id=user_id)

        async def list_recent_transactions(self, _advisor_id):
            return []

        async def count_customers(self, _advisor_id):
            return 1

        async def sum_total_aum(self, _advisor_id):
            return Decimal("10000")

        async def sum_monthly_sip_amount(self, _advisor_id):
            return Decimal("5000")

        async def count_pending_kyc_customers(self, _advisor_id):
            return 0

        async def count_active_sips(self, _advisor_id):
            return 2

    service = AdvisorService(FakeDb())
    service.advisors = FakeAdvisorDashboardRepository()

    summary = await service.dashboard_summary(advisor_user)

    assert summary.monthly_sip_amount == Decimal("5000")
    assert summary.active_sips == 2


def test_sip_routes_delegate_to_services(monkeypatch: pytest.MonkeyPatch) -> None:
    current_user = make_user(UserRole.SUPER_ADMIN)
    sip = SIPRead(
        id=uuid4(),
        customer_id=uuid4(),
        advisor_id=uuid4(),
        folio_id=uuid4(),
        scheme_id=uuid4(),
        sip_amount=Decimal("2500"),
        frequency=SIPFrequency.MONTHLY,
        status=SIPStatus.ACTIVE,
        start_date=date(2026, 5, 1),
        end_date=None,
        next_due_date=date(2026, 6, 1),
        mandate_reference=None,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeSIPService:
        def __init__(self, _db) -> None:
            pass

        async def create_sip(self, _user, _payload):
            return sip

        async def list_sips(self, _user, **_filters):
            return [sip]

        async def get_sip(self, _user, _sip_id):
            return sip

        async def update_sip(self, _user, _sip_id, payload):
            return sip.model_copy(update=payload.model_dump(exclude_unset=True))

        async def delete_sip(self, _user, _sip_id):
            return None

        async def customer_sip_summary(self, _user, customer_id):
            return {
                "customer_id": customer_id,
                "active_sips": 1,
                "paused_sips": 0,
                "cancelled_sips": 0,
                "completed_sips": 0,
                "total_monthly_sip_amount": Decimal("2500"),
                "next_due_sip_date": date(2026, 6, 1),
            }

    async def fake_current_user():
        return current_user

    monkeypatch.setattr("app.routes.sips.SIPService", FakeSIPService)
    app.dependency_overrides[get_current_user] = fake_current_user
    client = TestClient(app)
    payload = {
        "customer_id": str(sip.customer_id),
        "folio_id": str(sip.folio_id),
        "scheme_id": str(sip.scheme_id),
        "sip_amount": "2500",
        "frequency": "MONTHLY",
        "start_date": "2026-05-01",
    }

    assert client.post("/api/sips", json=payload).status_code == 201
    assert client.get("/api/sips?limit=10&offset=0&status=ACTIVE&frequency=MONTHLY").status_code == 200
    assert client.get(f"/api/sips/{sip.id}").status_code == 200
    assert client.patch(f"/api/sips/{sip.id}", json={"status": "PAUSED"}).status_code == 200
    assert client.delete(f"/api/sips/{sip.id}").status_code == 204
    assert client.get(f"/api/customers/{sip.customer_id}/sip-summary").status_code == 200
