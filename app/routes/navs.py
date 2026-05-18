from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.nav import NAVCreate, NAVListItem, NAVRead, NAVUpdate
from app.services.nav_service import MutualFundNAVService

router = APIRouter(prefix="/navs", tags=["navs"])


@router.post("", response_model=NAVRead, status_code=status.HTTP_201_CREATED)
async def create_nav(
    payload: NAVCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> NAVRead:
    return await MutualFundNAVService(db).create_nav(current_user, payload)


@router.get("", response_model=list[NAVListItem])
async def list_navs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    scheme_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[NAVListItem]:
    return await MutualFundNAVService(db).list_navs(
        current_user,
        scheme_id=scheme_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/{nav_id}", response_model=NAVRead)
async def get_nav(
    nav_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> NAVRead:
    return await MutualFundNAVService(db).get_nav(current_user, nav_id)


@router.patch("/{nav_id}", response_model=NAVRead)
async def update_nav(
    nav_id: UUID,
    payload: NAVUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> NAVRead:
    return await MutualFundNAVService(db).update_nav(current_user, nav_id, payload)


@router.delete("/{nav_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_nav(
    nav_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    await MutualFundNAVService(db).delete_nav(current_user, nav_id)
