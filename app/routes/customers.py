from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.customer import CustomerKycStatus, CustomerRiskProfile
from app.schemas.customer import CustomerCreate, CustomerListItem, CustomerRead, CustomerUpdate
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> CustomerRead:
    return await CustomerService(db).create_customer(current_user, payload)


@router.get("", response_model=list[CustomerListItem])
async def list_customers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    kyc_status: CustomerKycStatus | None = None,
    risk_profile: CustomerRiskProfile | None = None,
    search: str | None = Query(default=None, min_length=1, max_length=255),
) -> list[CustomerListItem]:
    return await CustomerService(db).list_customers(
        current_user,
        limit=limit,
        offset=offset,
        kyc_status=kyc_status,
        risk_profile=risk_profile,
        search=search,
    )


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> CustomerRead:
    return await CustomerService(db).get_customer(current_user, customer_id)


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> CustomerRead:
    return await CustomerService(db).update_customer(current_user, customer_id, payload)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    await CustomerService(db).delete_customer(current_user, customer_id)
