from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.sip import SIPFrequency, SIPStatus
from app.schemas.sip import CustomerSIPSummary, SIPCreate, SIPListItem, SIPRead, SIPUpdate
from app.services.sip_service import SIPService

sips_router = APIRouter(prefix="/sips", tags=["sips"])
customer_sips_router = APIRouter(prefix="/customers", tags=["sip-summary"])


@sips_router.post("", response_model=SIPRead, status_code=status.HTTP_201_CREATED)
async def create_sip(
    payload: SIPCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SIPRead:
    return await SIPService(db).create_sip(current_user, payload)


@sips_router.get("", response_model=list[SIPListItem])
async def list_sips(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    customer_id: UUID | None = None,
    status: SIPStatus | None = None,
    frequency: SIPFrequency | None = None,
    next_due_before: date | None = None,
) -> list[SIPListItem]:
    return await SIPService(db).list_sips(
        current_user,
        limit=limit,
        offset=offset,
        customer_id=customer_id,
        status=status,
        frequency=frequency,
        next_due_before=next_due_before,
    )


@sips_router.get("/{sip_id}", response_model=SIPRead)
async def get_sip(
    sip_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SIPRead:
    return await SIPService(db).get_sip(current_user, sip_id)


@sips_router.patch("/{sip_id}", response_model=SIPRead)
async def update_sip(
    sip_id: UUID,
    payload: SIPUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SIPRead:
    return await SIPService(db).update_sip(current_user, sip_id, payload)


@sips_router.delete("/{sip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sip(
    sip_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    await SIPService(db).delete_sip(current_user, sip_id)


@customer_sips_router.get("/{customer_id}/sip-summary", response_model=CustomerSIPSummary)
async def get_customer_sip_summary(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> CustomerSIPSummary:
    return await SIPService(db).customer_sip_summary(current_user, customer_id)
