from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.portfolio import (
    FolioCreate,
    FolioRead,
    FolioUpdate,
    MutualFundSchemeCreate,
    MutualFundSchemeRead,
    MutualFundSchemeUpdate,
    PortfolioHoldingCreate,
    PortfolioHoldingRead,
    PortfolioHoldingUpdate,
    PortfolioSummaryRead,
)
from app.services.portfolio_service import FolioService, MutualFundSchemeService, PortfolioHoldingService

schemes_router = APIRouter(prefix="/schemes", tags=["schemes"])
folios_router = APIRouter(prefix="/folios", tags=["folios"])
holdings_router = APIRouter(prefix="/portfolio-holdings", tags=["portfolio-holdings"])
summary_router = APIRouter(prefix="/customers", tags=["portfolio-summary"])


@schemes_router.post("", response_model=MutualFundSchemeRead, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    payload: MutualFundSchemeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> MutualFundSchemeRead:
    return await MutualFundSchemeService(db).create_scheme(current_user, payload)


@schemes_router.get("", response_model=list[MutualFundSchemeRead])
async def list_schemes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[MutualFundSchemeRead]:
    return await MutualFundSchemeService(db).list_schemes(current_user, limit=limit, offset=offset)


@schemes_router.get("/{scheme_id}", response_model=MutualFundSchemeRead)
async def get_scheme(
    scheme_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> MutualFundSchemeRead:
    return await MutualFundSchemeService(db).get_scheme(current_user, scheme_id)


@schemes_router.patch("/{scheme_id}", response_model=MutualFundSchemeRead)
async def update_scheme(
    scheme_id: UUID,
    payload: MutualFundSchemeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> MutualFundSchemeRead:
    return await MutualFundSchemeService(db).update_scheme(current_user, scheme_id, payload)


@schemes_router.delete("/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheme(
    scheme_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    await MutualFundSchemeService(db).delete_scheme(current_user, scheme_id)


@folios_router.post("", response_model=FolioRead, status_code=status.HTTP_201_CREATED)
async def create_folio(
    payload: FolioCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> FolioRead:
    return await FolioService(db).create_folio(current_user, payload)


@folios_router.get("", response_model=list[FolioRead])
async def list_folios(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[FolioRead]:
    return await FolioService(db).list_folios(current_user, limit=limit, offset=offset)


@folios_router.get("/{folio_id}", response_model=FolioRead)
async def get_folio(
    folio_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> FolioRead:
    return await FolioService(db).get_folio(current_user, folio_id)


@folios_router.patch("/{folio_id}", response_model=FolioRead)
async def update_folio(
    folio_id: UUID,
    payload: FolioUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> FolioRead:
    return await FolioService(db).update_folio(current_user, folio_id, payload)


@folios_router.delete("/{folio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folio(
    folio_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    await FolioService(db).delete_folio(current_user, folio_id)


@holdings_router.post("", response_model=PortfolioHoldingRead, status_code=status.HTTP_201_CREATED)
async def create_holding(
    payload: PortfolioHoldingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> PortfolioHoldingRead:
    return await PortfolioHoldingService(db).create_holding(current_user, payload)


@holdings_router.get("", response_model=list[PortfolioHoldingRead])
async def list_holdings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PortfolioHoldingRead]:
    return await PortfolioHoldingService(db).list_holdings(current_user, limit=limit, offset=offset)


@holdings_router.get("/{holding_id}", response_model=PortfolioHoldingRead)
async def get_holding(
    holding_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> PortfolioHoldingRead:
    return await PortfolioHoldingService(db).get_holding(current_user, holding_id)


@holdings_router.patch("/{holding_id}", response_model=PortfolioHoldingRead)
async def update_holding(
    holding_id: UUID,
    payload: PortfolioHoldingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> PortfolioHoldingRead:
    return await PortfolioHoldingService(db).update_holding(current_user, holding_id, payload)


@holdings_router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    holding_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    await PortfolioHoldingService(db).delete_holding(current_user, holding_id)


@summary_router.get("/{customer_id}/portfolio-summary", response_model=PortfolioSummaryRead)
async def get_customer_portfolio_summary(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> PortfolioSummaryRead:
    return await PortfolioHoldingService(db).customer_portfolio_summary(current_user, customer_id)
