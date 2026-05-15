from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.exceptions import NotFoundException
from app.main import app
from app.models.advisor import AdvisorComplianceStatus, AdvisorLicenseType, AdvisorOnboardingStatus
from app.models.user import UserRole
from app.schemas.advisor import AdvisorDashboardSummary, AdvisorRead
from app.services.advisor_service import AdvisorService


def make_user(role: UserRole = UserRole.ADVISOR):
    return SimpleNamespace(id=uuid4(), role=role, is_active=True)


def make_advisor_read(user_id=None) -> AdvisorRead:
    now = datetime.now(UTC)
    return AdvisorRead(
        id=uuid4(),
        user_id=user_id or uuid4(),
        firm_name="MF Advisory",
        arn_number="ARN12345",
        ria_number=None,
        license_type=AdvisorLicenseType.ARN,
        target_region="West India",
        business_address="123 Finance Street, Mumbai",
        compliance_status=AdvisorComplianceStatus.PENDING,
        onboarding_status=AdvisorOnboardingStatus.IN_PROGRESS,
        created_at=now,
        updated_at=now,
    )


def advisor_payload() -> dict[str, str]:
    return {
        "firm_name": "MF Advisory",
        "arn_number": "ARN12345",
        "license_type": "ARN",
        "target_region": "West India",
        "business_address": "123 Finance Street, Mumbai",
    }


def test_advisor_profile_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    current_user = make_user(UserRole.ADVISOR)

    class FakeAdvisorService:
        def __init__(self, _db) -> None:
            pass

        async def create_profile(self, user, _payload):
            return make_advisor_read(user.id)

        async def get_profile(self, user):
            return make_advisor_read(user.id)

        async def update_profile(self, user, payload):
            advisor = make_advisor_read(user.id)
            return advisor.model_copy(update=payload.model_dump(exclude_unset=True))

        async def dashboard_summary(self, _user):
            return AdvisorDashboardSummary(
                total_customers=4,
                total_aum=Decimal("1250000.50"),
                monthly_sip_amount=Decimal("35000"),
                pending_kyc_customers=1,
                active_sips=7,
                recent_transactions=[],
            )

    async def fake_current_user():
        return current_user

    monkeypatch.setattr("app.routes.advisors.AdvisorService", FakeAdvisorService)
    app.dependency_overrides[get_current_user] = fake_current_user
    client = TestClient(app)

    create_response = client.post("/api/advisors/profile", json=advisor_payload())
    assert create_response.status_code == 201
    assert create_response.json()["user_id"] == str(current_user.id)

    get_response = client.get("/api/advisors/profile")
    assert get_response.status_code == 200
    assert get_response.json()["firm_name"] == "MF Advisory"

    patch_response = client.patch("/api/advisors/profile", json={"target_region": "South India"})
    assert patch_response.status_code == 200
    assert patch_response.json()["target_region"] == "South India"

    dashboard_response = client.get("/api/advisors/dashboard-summary")
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["total_customers"] == 4
    assert dashboard_response.json()["pending_kyc_customers"] == 1


def test_advisor_routes_reject_customer_role() -> None:
    async def fake_current_user():
        return make_user(UserRole.CUSTOMER)

    app.dependency_overrides[get_current_user] = fake_current_user
    client = TestClient(app)

    response = client.get("/api/advisors/profile")

    assert response.status_code == 403


def test_advisor_profile_validation_requires_matching_license_number() -> None:
    async def fake_current_user():
        return make_user(UserRole.ADVISOR)

    app.dependency_overrides[get_current_user] = fake_current_user
    client = TestClient(app)

    response = client.post(
        "/api/advisors/profile",
        json={
            "firm_name": "RIA Firm",
            "license_type": "RIA",
            "target_region": "West India",
            "business_address": "123 Finance Street, Mumbai",
        },
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_advisor_dashboard_requires_profile_for_advisor() -> None:
    class FakeAdvisorRepository:
        def __init__(self, _db) -> None:
            pass

        async def get_by_user_id(self, _user_id):
            return None

    service = AdvisorService(db=SimpleNamespace())
    service.advisors = FakeAdvisorRepository(None)

    with pytest.raises(NotFoundException):
        await service.dashboard_summary(make_user(UserRole.ADVISOR))


@pytest.mark.anyio
async def test_super_admin_dashboard_can_return_global_summary() -> None:
    class FakeAdvisorRepository:
        async def list_recent_transactions(self, advisor_id):
            assert advisor_id is None
            return []

        async def count_customers(self, advisor_id):
            assert advisor_id is None
            return 12

        async def sum_total_aum(self, advisor_id):
            assert advisor_id is None
            return Decimal("900000")

        async def sum_monthly_sip_amount(self, advisor_id):
            assert advisor_id is None
            return Decimal("45000")

        async def count_pending_kyc_customers(self, advisor_id):
            assert advisor_id is None
            return 2

        async def count_active_sips(self, advisor_id):
            assert advisor_id is None
            return 8

    service = AdvisorService(db=SimpleNamespace())
    service.advisors = FakeAdvisorRepository()

    summary = await service.dashboard_summary(make_user(UserRole.SUPER_ADMIN))

    assert summary.total_customers == 12
    assert summary.total_aum == Decimal("900000")
    assert summary.monthly_sip_amount == Decimal("45000")
    assert summary.pending_kyc_customers == 2
    assert summary.active_sips == 8
