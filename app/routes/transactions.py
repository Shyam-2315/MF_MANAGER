from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.transaction import TransactionStatus, TransactionType
from app.schemas.transaction import (
    CustomerTransactionSummary,
    TransactionCreate,
    TransactionListItem,
    TransactionRead,
    TransactionUpdate,
)
from app.services.transaction_service import InvestmentTransactionService

transactions_router = APIRouter(prefix="/transactions", tags=["transactions"])
customer_transactions_router = APIRouter(prefix="/customers", tags=["transaction-summary"])


@transactions_router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> TransactionRead:
    return await InvestmentTransactionService(db).create_transaction(current_user, payload)


@transactions_router.get("", response_model=list[TransactionListItem])
async def list_transactions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    customer_id: UUID | None = None,
    scheme_id: UUID | None = None,
    transaction_type: TransactionType | None = None,
    transaction_status: TransactionStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TransactionListItem]:
    return await InvestmentTransactionService(db).list_transactions(
        current_user,
        limit=limit,
        offset=offset,
        customer_id=customer_id,
        scheme_id=scheme_id,
        transaction_type=transaction_type,
        transaction_status=transaction_status,
        date_from=date_from,
        date_to=date_to,
    )


@transactions_router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(
    transaction_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> TransactionRead:
    return await InvestmentTransactionService(db).get_transaction(current_user, transaction_id)


@transactions_router.patch("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: UUID,
    payload: TransactionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> TransactionRead:
    return await InvestmentTransactionService(db).update_transaction(current_user, transaction_id, payload)


@transactions_router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    await InvestmentTransactionService(db).delete_transaction(current_user, transaction_id)


@customer_transactions_router.get("/{customer_id}/transaction-summary", response_model=CustomerTransactionSummary)
async def get_customer_transaction_summary(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> CustomerTransactionSummary:
    return await InvestmentTransactionService(db).customer_transaction_summary(current_user, customer_id)
