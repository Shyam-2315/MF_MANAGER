from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import RoleChecker
from app.models.user import User, UserRole
from app.schemas.advisor import AdvisorCreate, AdvisorDashboardSummary, AdvisorRead, AdvisorUpdate
from app.services.advisor_service import AdvisorService

router = APIRouter(prefix="/advisors", tags=["advisors"])
require_advisor_access = RoleChecker(UserRole.ADVISOR, UserRole.SUPER_ADMIN)


@router.post("/profile", response_model=AdvisorRead, status_code=status.HTTP_201_CREATED)
async def create_advisor_profile(
    payload: AdvisorCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_advisor_access)],
) -> AdvisorRead:
    return await AdvisorService(db).create_profile(current_user, payload)


@router.get("/profile", response_model=AdvisorRead)
async def get_advisor_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_advisor_access)],
) -> AdvisorRead:
    return await AdvisorService(db).get_profile(current_user)


@router.patch("/profile", response_model=AdvisorRead)
async def update_advisor_profile(
    payload: AdvisorUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_advisor_access)],
) -> AdvisorRead:
    return await AdvisorService(db).update_profile(current_user, payload)


@router.get("/dashboard-summary", response_model=AdvisorDashboardSummary)
async def get_advisor_dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_advisor_access)],
) -> AdvisorDashboardSummary:
    return await AdvisorService(db).dashboard_summary(current_user)
