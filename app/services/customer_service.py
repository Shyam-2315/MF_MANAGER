from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.customer import Customer, CustomerKycStatus, CustomerRiskProfile
from app.models.user import User, UserRole
from app.repositories.advisor_repository import AdvisorRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.advisors = AdvisorRepository(db)

    async def create_customer(self, current_user: User, payload: CustomerCreate) -> Customer:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")

        advisor_id = await self._resolve_write_advisor_id(current_user, payload.advisor_id)
        await self._validate_unique_customer_identity(
            advisor_id=advisor_id,
            email=str(payload.email),
            pan_number=payload.pan_number,
        )

        try:
            customer = await self.customers.create_customer(advisor_id=advisor_id, data=payload.model_dump())
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("Customer PAN or email conflicts with an existing customer") from exc

        await self.db.refresh(customer)
        return customer

    async def list_customers(
        self,
        current_user: User,
        *,
        limit: int = 50,
        offset: int = 0,
        kyc_status: CustomerKycStatus | None = None,
        risk_profile: CustomerRiskProfile | None = None,
        search: str | None = None,
    ) -> list[Customer]:
        advisor_id = await self._resolve_read_advisor_id(current_user)
        return await self.customers.list_customers(
            advisor_id=advisor_id,
            limit=limit,
            offset=offset,
            kyc_status=kyc_status,
            risk_profile=risk_profile,
            search=search,
        )

    async def get_customer(self, current_user: User, customer_id: UUID) -> Customer:
        customer = await self.customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundException("Customer not found")
        await self._assert_can_read_customer(current_user, customer)
        return customer

    async def update_customer(self, current_user: User, customer_id: UUID, payload: CustomerUpdate) -> Customer:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")

        customer = await self.get_customer(current_user, customer_id)
        update_data = payload.model_dump(exclude_unset=True)
        if "email" in update_data:
            existing_email = await self.customers.get_by_email_for_advisor(
                advisor_id=customer.advisor_id,
                email=str(update_data["email"]),
            )
            if existing_email is not None and existing_email.id != customer.id:
                raise BadRequestException("A customer with this email already exists for this advisor")
        if "pan_number" in update_data:
            existing_pan = await self.customers.get_by_pan(update_data["pan_number"])
            if existing_pan is not None and existing_pan.id != customer.id:
                raise BadRequestException("A customer with this PAN already exists")

        try:
            updated_customer = await self.customers.update_customer(customer, update_data)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise BadRequestException("Customer PAN or email conflicts with an existing customer") from exc

        await self.db.refresh(updated_customer)
        return updated_customer

    async def delete_customer(self, current_user: User, customer_id: UUID) -> None:
        if current_user.role not in {UserRole.ADVISOR, UserRole.SUPER_ADMIN}:
            raise ForbiddenException("Insufficient permissions")

        customer = await self.get_customer(current_user, customer_id)
        await self.customers.soft_delete_customer(customer)
        await self.db.commit()

    async def _resolve_write_advisor_id(self, current_user: User, requested_advisor_id: UUID | None) -> UUID:
        if current_user.role == UserRole.SUPER_ADMIN:
            if requested_advisor_id is None:
                raise BadRequestException("advisor_id is required when creating a customer as SUPER_ADMIN")
            return requested_advisor_id

        advisor = await self.advisors.get_by_user_id(current_user.id)
        if advisor is None:
            raise NotFoundException("Advisor profile not found")
        return advisor.id

    async def _resolve_read_advisor_id(self, current_user: User) -> UUID | None:
        if current_user.role in {UserRole.SUPER_ADMIN, UserRole.COMPLIANCE}:
            return None
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            return advisor.id
        raise ForbiddenException("Insufficient permissions")

    async def _assert_can_read_customer(self, current_user: User, customer: Customer) -> None:
        if current_user.role in {UserRole.SUPER_ADMIN, UserRole.COMPLIANCE}:
            return
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.advisors.get_by_user_id(current_user.id)
            if advisor is None:
                raise NotFoundException("Advisor profile not found")
            if customer.advisor_id != advisor.id:
                raise NotFoundException("Customer not found")
            return
        raise ForbiddenException("Insufficient permissions")

    async def _validate_unique_customer_identity(self, *, advisor_id: UUID, email: str, pan_number: str) -> None:
        if await self.customers.get_by_pan(pan_number) is not None:
            raise BadRequestException("A customer with this PAN already exists")
        if await self.customers.get_by_email_for_advisor(advisor_id=advisor_id, email=email) is not None:
            raise BadRequestException("A customer with this email already exists for this advisor")
