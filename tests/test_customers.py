from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.main import app
from app.models.customer import Customer, CustomerKycStatus, CustomerRiskProfile
from app.models.user import UserRole
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.advisor_service import AdvisorService
from app.services.customer_service import CustomerService


def make_user(role: UserRole = UserRole.ADVISOR, user_id: UUID | None = None):
    return SimpleNamespace(id=user_id or uuid4(), role=role, is_active=True)


def make_advisor(advisor_id: UUID | None = None, user_id: UUID | None = None):
    return SimpleNamespace(id=advisor_id or uuid4(), user_id=user_id or uuid4())


def make_customer(
    *,
    customer_id: UUID | None = None,
    advisor_id: UUID | None = None,
    email: str = "customer@example.com",
    pan_number: str = "ABCDE1234F",
    kyc_status: CustomerKycStatus = CustomerKycStatus.PENDING,
    is_active: bool = True,
):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=customer_id or uuid4(),
        advisor_id=advisor_id or uuid4(),
        full_name="Test Customer",
        email=email,
        phone="+15555550123",
        pan_number=pan_number,
        date_of_birth=date(1990, 1, 1),
        address="123 Finance Street",
        kyc_status=kyc_status,
        risk_profile=CustomerRiskProfile.MODERATE,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def customer_payload(**overrides):
    payload = {
        "full_name": "Test Customer",
        "email": "customer@example.com",
        "phone": "+15555550123",
        "pan_number": "ABCDE1234F",
        "date_of_birth": "1990-01-01",
        "address": "123 Finance Street",
        "risk_profile": "MODERATE",
    }
    payload.update(overrides)
    return payload


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

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
        self.created_with = None

    async def create_customer(self, *, advisor_id, data):
        customer = make_customer(advisor_id=advisor_id, email=str(data["email"]), pan_number=data["pan_number"])
        self.customers.append(customer)
        self.created_with = {"advisor_id": advisor_id, "data": data}
        return customer

    async def get_by_id(self, customer_id, *, active_only=True):
        for customer in self.customers:
            if customer.id == customer_id and (not active_only or customer.is_active):
                return customer
        return None

    async def get_by_pan(self, pan_number, *, active_only=True):
        for customer in self.customers:
            if customer.pan_number == pan_number.upper() and (not active_only or customer.is_active):
                return customer
        return None

    async def get_by_email_for_advisor(self, *, advisor_id, email, active_only=True):
        for customer in self.customers:
            if customer.advisor_id == advisor_id and customer.email == email.lower() and (not active_only or customer.is_active):
                return customer
        return None

    async def list_customers(self, *, advisor_id=None, **_kwargs):
        return [
            customer
            for customer in self.customers
            if customer.is_active and (advisor_id is None or customer.advisor_id == advisor_id)
        ]

    async def update_customer(self, customer, data):
        for field, value in data.items():
            setattr(customer, field, value)
        return customer

    async def soft_delete_customer(self, customer):
        customer.is_active = False
        return customer


def make_customer_service(*, advisor_repo=None, customer_repo=None, db=None) -> CustomerService:
    service = CustomerService(db=db or FakeDb())
    service.advisors = advisor_repo or FakeAdvisorRepository()
    service.customers = customer_repo or FakeCustomerRepository()
    return service


def test_customer_model_and_migration_are_registered() -> None:
    columns = Customer.__table__.columns

    assert "advisor_id" in columns
    assert Customer.__table__.c.pan_number.unique is True
    assert any(constraint.name == "uq_customers_advisor_email" for constraint in Customer.__table__.constraints)
    assert CustomerKycStatus.PENDING.value == "PENDING"
    assert CustomerRiskProfile.MODERATE.value == "MODERATE"


def test_customer_routes_show_in_swagger() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()

    assert "/api/customers" in schema["paths"]
    assert "/api/customers/{customer_id}" in schema["paths"]


@pytest.mark.anyio
async def test_advisor_can_create_customer() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    service = make_customer_service(advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}))

    customer = await service.create_customer(advisor_user, CustomerCreate(**customer_payload()))

    assert customer.advisor_id == advisor.id
    assert customer.kyc_status == CustomerKycStatus.PENDING


@pytest.mark.anyio
async def test_advisor_cannot_access_another_advisors_customer() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    own_advisor = make_advisor(user_id=advisor_user.id)
    other_customer = make_customer(advisor_id=uuid4())
    service = make_customer_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: own_advisor}),
        customer_repo=FakeCustomerRepository([other_customer]),
    )

    with pytest.raises(NotFoundException):
        await service.get_customer(advisor_user, other_customer.id)


@pytest.mark.anyio
async def test_super_admin_can_access_all_customers() -> None:
    customer = make_customer()
    service = make_customer_service(customer_repo=FakeCustomerRepository([customer]))

    result = await service.get_customer(make_user(UserRole.SUPER_ADMIN), customer.id)
    listed = await service.list_customers(make_user(UserRole.SUPER_ADMIN))

    assert result.id == customer.id
    assert listed == [customer]


@pytest.mark.anyio
async def test_compliance_can_list_and_read_but_cannot_write() -> None:
    customer = make_customer()
    compliance_user = make_user(UserRole.COMPLIANCE)
    service = make_customer_service(customer_repo=FakeCustomerRepository([customer]))

    assert await service.get_customer(compliance_user, customer.id) == customer
    assert await service.list_customers(compliance_user) == [customer]

    with pytest.raises(ForbiddenException):
        await service.create_customer(compliance_user, CustomerCreate(**customer_payload()))
    with pytest.raises(ForbiddenException):
        await service.update_customer(compliance_user, customer.id, CustomerUpdate(full_name="New Name"))
    with pytest.raises(ForbiddenException):
        await service.delete_customer(compliance_user, customer.id)


@pytest.mark.anyio
async def test_customer_role_cannot_access_customer_management() -> None:
    service = make_customer_service()
    customer_user = make_user(UserRole.CUSTOMER)

    with pytest.raises(ForbiddenException):
        await service.list_customers(customer_user)
    with pytest.raises(ForbiddenException):
        await service.create_customer(customer_user, CustomerCreate(**customer_payload()))


@pytest.mark.anyio
async def test_duplicate_pan_rejected() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    existing = make_customer(advisor_id=advisor.id, pan_number="ABCDE1234F")
    service = make_customer_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([existing]),
    )

    with pytest.raises(BadRequestException):
        await service.create_customer(advisor_user, CustomerCreate(**customer_payload()))


@pytest.mark.anyio
async def test_duplicate_email_for_same_advisor_rejected() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    existing = make_customer(advisor_id=advisor.id, email="customer@example.com", pan_number="ZZZZZ9999Z")
    service = make_customer_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([existing]),
    )

    with pytest.raises(BadRequestException):
        await service.create_customer(advisor_user, CustomerCreate(**customer_payload(pan_number="ABCDE1234F")))


@pytest.mark.anyio
async def test_same_email_allowed_under_different_advisor() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    existing = make_customer(advisor_id=uuid4(), email="customer@example.com", pan_number="ZZZZZ9999Z")
    service = make_customer_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([existing]),
    )

    customer = await service.create_customer(advisor_user, CustomerCreate(**customer_payload(pan_number="ABCDE1234F")))

    assert customer.email == "customer@example.com"
    assert customer.advisor_id == advisor.id


@pytest.mark.anyio
async def test_soft_delete_hides_customer_from_list() -> None:
    advisor_user = make_user(UserRole.ADVISOR)
    advisor = make_advisor(user_id=advisor_user.id)
    customer = make_customer(advisor_id=advisor.id)
    service = make_customer_service(
        advisor_repo=FakeAdvisorRepository({advisor_user.id: advisor}),
        customer_repo=FakeCustomerRepository([customer]),
    )

    await service.delete_customer(advisor_user, customer.id)

    assert customer.is_active is False
    assert await service.list_customers(advisor_user) == []


@pytest.mark.anyio
async def test_dashboard_uses_customer_counts() -> None:
    advisor_id = uuid4()
    advisor_user = make_user(UserRole.ADVISOR)

    class FakeAdvisorDashboardRepository:
        async def get_by_user_id(self, user_id):
            assert user_id == advisor_user.id
            return make_advisor(advisor_id=advisor_id, user_id=user_id)

        async def list_recent_transactions(self, requested_advisor_id):
            assert requested_advisor_id == advisor_id
            return []

        async def count_customers(self, requested_advisor_id):
            assert requested_advisor_id == advisor_id
            return 2

        async def sum_total_aum(self, requested_advisor_id):
            assert requested_advisor_id == advisor_id
            return 0

        async def sum_monthly_sip_amount(self, requested_advisor_id):
            assert requested_advisor_id == advisor_id
            return 0

        async def count_pending_kyc_customers(self, requested_advisor_id):
            assert requested_advisor_id == advisor_id
            return 1

        async def count_active_sips(self, requested_advisor_id):
            assert requested_advisor_id == advisor_id
            return 0

    service = AdvisorService(db=SimpleNamespace())
    service.advisors = FakeAdvisorDashboardRepository()

    summary = await service.dashboard_summary(advisor_user)

    assert summary.total_customers == 2
    assert summary.pending_kyc_customers == 1


def test_customer_routes_delegate_to_service(monkeypatch: pytest.MonkeyPatch) -> None:
    current_user = make_user(UserRole.ADVISOR)
    customer = CustomerRead(**customer_payload(), id=uuid4(), advisor_id=uuid4(), is_active=True, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

    class FakeCustomerService:
        def __init__(self, _db) -> None:
            pass

        async def create_customer(self, _user, _payload):
            return customer

        async def list_customers(self, _user, **_filters):
            return [customer]

        async def get_customer(self, _user, _customer_id):
            return customer

        async def update_customer(self, _user, _customer_id, payload):
            return customer.model_copy(update=payload.model_dump(exclude_unset=True))

        async def delete_customer(self, _user, _customer_id):
            return None

    async def fake_current_user():
        return current_user

    monkeypatch.setattr("app.routes.customers.CustomerService", FakeCustomerService)
    app.dependency_overrides[get_current_user] = fake_current_user
    client = TestClient(app)

    create_response = client.post("/api/customers", json=customer_payload())
    assert create_response.status_code == 201

    list_response = client.get("/api/customers?limit=10&offset=0&kyc_status=PENDING&search=Test")
    assert list_response.status_code == 200
    assert list_response.json()[0]["pan_number"] == "ABCDE1234F"

    get_response = client.get(f"/api/customers/{customer.id}")
    assert get_response.status_code == 200

    patch_response = client.patch(f"/api/customers/{customer.id}", json={"kyc_status": "VERIFIED"})
    assert patch_response.status_code == 200
    assert patch_response.json()["kyc_status"] == "VERIFIED"

    delete_response = client.delete(f"/api/customers/{customer.id}")
    assert delete_response.status_code == 204
