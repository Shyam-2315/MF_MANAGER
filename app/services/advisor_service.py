from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.models.advisor import Advisor
from app.models.user import User, UserRole
from app.repositories.advisor_repository import AdvisorRepository
from app.schemas.advisor import AdvisorCreate, AdvisorDashboardSummary, AdvisorUpdate


class AdvisorService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.advisors = AdvisorRepository(db)

    async def create_profile(self, current_user: User, payload: AdvisorCreate) -> Advisor:
        existing_profile = await self.advisors.get_by_user_id(current_user.id)
        if existing_profile is not None:
            raise ConflictException("Advisor profile already exists")

        try:
            advisor = await self.advisors.create(user_id=current_user.id, data=payload.model_dump())
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictException("Advisor profile conflicts with an existing ARN or RIA number") from exc

        await self.db.refresh(advisor)
        return advisor

    async def get_profile(self, current_user: User) -> Advisor:
        advisor = await self.advisors.get_by_user_id(current_user.id)
        if advisor is None:
            raise NotFoundException("Advisor profile not found")
        return advisor

    async def update_profile(self, current_user: User, payload: AdvisorUpdate) -> Advisor:
        advisor = await self.get_profile(current_user)
        update_data = payload.model_dump(exclude_unset=True)
        self._validate_license_state(advisor, update_data)

        try:
            updated_advisor = await self.advisors.update(advisor, update_data)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictException("Advisor profile conflicts with an existing ARN or RIA number") from exc

        await self.db.refresh(updated_advisor)
        return updated_advisor

    async def dashboard_summary(self, current_user: User) -> AdvisorDashboardSummary:
        advisor_id = None
        if current_user.role == UserRole.ADVISOR:
            advisor = await self.get_profile(current_user)
            advisor_id = advisor.id

        recent_transactions = await self.advisors.list_recent_transactions(advisor_id)
        return AdvisorDashboardSummary(
            total_customers=await self.advisors.count_customers(advisor_id),
            total_aum=await self.advisors.sum_total_aum(advisor_id),
            monthly_sip_amount=await self.advisors.sum_monthly_sip_amount(advisor_id),
            pending_kyc_customers=await self.advisors.count_pending_kyc_customers(advisor_id),
            active_sips=await self.advisors.count_active_sips(advisor_id),
            recent_transactions=recent_transactions,
        )

    def _validate_license_state(self, advisor: Advisor, update_data: dict[str, Any]) -> None:
        license_type = update_data.get("license_type", advisor.license_type)
        arn_number = update_data.get("arn_number", advisor.arn_number)
        ria_number = update_data.get("ria_number", advisor.ria_number)
        license_value = license_type.value if hasattr(license_type, "value") else str(license_type)

        if license_value in {"ARN", "ARN_RIA"} and not arn_number:
            raise ConflictException("arn_number is required for ARN license types")
        if license_value in {"RIA", "ARN_RIA"} and not ria_number:
            raise ConflictException("ria_number is required for RIA license types")
