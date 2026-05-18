from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dependencies import get_current_user
from app.exceptions import BadRequestException, ForbiddenException
from app.main import app
from app.models.user import UserRole
from app.schemas.nav import NAVCreate
from app.services.nav_service import MutualFundNAVService
from app.services.portfolio_service import PortfolioHoldingService


def make_user(role: UserRole) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=role, is_active=True)


class FakeDb:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, _entity) -> None:
        return None


@pytest.mark.anyio
async def test_create_nav_duplicate_rejected_and_negative_nav_rejected() -> None:
    service = MutualFundNAVService(FakeDb())
    scheme_id = uuid4()
    nav = SimpleNamespace(id=uuid4(), scheme_id=scheme_id, nav_date=date(2026, 5, 18), nav_value=Decimal("123.4567"), is_active=True)
    service.schemes = SimpleNamespace(get_by_id=lambda _id: nav)
    created: list[SimpleNamespace] = []

    async def get_scheme(_id):
        return nav

    async def get_by_scheme_and_date(*, scheme_id, nav_date, active_only=True):
        return next((item for item in created if item.scheme_id == scheme_id and item.nav_date == nav_date and item.is_active), None)

    async def create(data):
        row = SimpleNamespace(id=uuid4(), is_active=True, created_at=datetime.now(UTC), updated_at=datetime.now(UTC), **data)
        created.append(row)
        return row

    service.schemes = SimpleNamespace(get_by_id=get_scheme)
    service.navs = SimpleNamespace(get_by_scheme_and_date=get_by_scheme_and_date, create=create)

    created_nav = await service.create_nav(
        make_user(UserRole.SUPER_ADMIN),
        NAVCreate(scheme_id=scheme_id, nav_date=date(2026, 5, 18), nav_value=Decimal("100.1234")),
    )
    assert created_nav.nav_value == Decimal("100.1234")

    with pytest.raises(BadRequestException):
        await service.create_nav(
            make_user(UserRole.SUPER_ADMIN),
            NAVCreate(scheme_id=scheme_id, nav_date=date(2026, 5, 18), nav_value=Decimal("120.1234")),
        )

    with pytest.raises(ValidationError):
        NAVCreate(scheme_id=scheme_id, nav_date=date(2026, 5, 19), nav_value=Decimal("-1"))


@pytest.mark.anyio
async def test_latest_nav_fetched_correctly() -> None:
    service = MutualFundNAVService(FakeDb())
    nav_latest = SimpleNamespace(id=uuid4(), scheme_id=uuid4(), nav_date=date(2026, 5, 18), nav_value=Decimal("111.1"), is_active=True)

    async def get_latest(_scheme_id):
        return nav_latest

    service.navs = SimpleNamespace(get_latest_nav_for_scheme=get_latest)
    latest = await service.navs.get_latest_nav_for_scheme(uuid4())
    assert latest.nav_date == date(2026, 5, 18)


@pytest.mark.anyio
async def test_nav_rbac_read_only_for_advisor_compliance_and_customer_blocked() -> None:
    service = MutualFundNAVService(FakeDb())
    row = SimpleNamespace(id=uuid4(), scheme_id=uuid4(), nav_date=date(2026, 5, 18), nav_value=Decimal("100"), is_active=True)

    async def list_by_scheme(**_kwargs):
        return [row]

    async def get_by_id(_id, active_only=True):
        return row

    service.navs = SimpleNamespace(list_by_scheme=list_by_scheme, get_by_id=get_by_id)

    assert len(await service.list_navs(make_user(UserRole.ADVISOR))) == 1
    assert len(await service.list_navs(make_user(UserRole.COMPLIANCE))) == 1

    with pytest.raises(ForbiddenException):
        await service.delete_nav(make_user(UserRole.ADVISOR), row.id)
    with pytest.raises(ForbiddenException):
        await service.list_navs(make_user(UserRole.CUSTOMER))


@pytest.mark.anyio
async def test_recalculate_valuations_updates_holdings() -> None:
    advisor_id = uuid4()
    service = PortfolioHoldingService(FakeDb())
    holdings = [
        SimpleNamespace(
            id=uuid4(),
            advisor_id=advisor_id,
            scheme_id=uuid4(),
            units=Decimal("10"),
            current_value=Decimal("0"),
            current_nav=None,
            valuation_date=None,
            is_active=True,
        )
    ]
    nav = SimpleNamespace(nav_value=Decimal("125.50"), nav_date=date(2026, 5, 18))

    async def get_by_user_id(_user_id):
        return SimpleNamespace(id=advisor_id)

    async def list_active_for_valuation(_advisor_id):
        return holdings

    async def get_latest_nav_for_scheme(_scheme_id):
        return nav

    service.advisors = SimpleNamespace(get_by_user_id=get_by_user_id)
    service.holdings = SimpleNamespace(list_active_for_valuation=list_active_for_valuation)
    service.navs = SimpleNamespace(get_latest_nav_for_scheme=get_latest_nav_for_scheme)
    result = await service.recalculate_valuations(make_user(UserRole.ADVISOR))

    assert result.holdings_updated == 1
    assert result.total_current_value == Decimal("1255.00")
    assert holdings[0].current_nav == Decimal("125.50")
    assert holdings[0].valuation_date == date(2026, 5, 18)


def test_swagger_exposes_nav_and_recalculation_routes() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/navs" in schema["paths"]
    assert "/api/navs/{nav_id}" in schema["paths"]
    assert "/api/portfolio-holdings/recalculate-valuations" in schema["paths"]


def test_nav_routes_delegate_and_customer_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {
        "id": str(uuid4()),
        "scheme_id": str(uuid4()),
        "nav_date": "2026-05-18",
        "nav_value": "123.4500",
        "source": "manual",
        "is_active": True,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    class FakeNavService:
        def __init__(self, _db) -> None:
            pass

        async def create_nav(self, _user, _payload):
            return row

        async def list_navs(self, _user, **_kwargs):
            return [row]

        async def get_nav(self, _user, _nav_id):
            return row

        async def update_nav(self, _user, _nav_id, _payload):
            return row

        async def delete_nav(self, _user, _nav_id):
            return None

    async def super_admin_user():
        return make_user(UserRole.SUPER_ADMIN)

    monkeypatch.setattr("app.routes.navs.MutualFundNAVService", FakeNavService)
    app.dependency_overrides[get_current_user] = super_admin_user
    client = TestClient(app)
    assert client.post("/api/navs", json={"scheme_id": str(uuid4()), "nav_date": "2026-05-18", "nav_value": "101.1234"}).status_code == 201
    assert client.get("/api/navs").status_code == 200
