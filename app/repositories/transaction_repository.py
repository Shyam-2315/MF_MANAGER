from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import InvestmentTransaction, TransactionStatus, TransactionType


class InvestmentTransactionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict[str, Any]) -> InvestmentTransaction:
        transaction = InvestmentTransaction(**data)
        self.db.add(transaction)
        await self.db.flush()
        return transaction

    async def get_by_id(
        self,
        transaction_id: UUID,
        *,
        active_only: bool = True,
    ) -> InvestmentTransaction | None:
        statement = select(InvestmentTransaction).where(InvestmentTransaction.id == transaction_id)
        if active_only:
            statement = statement.where(InvestmentTransaction.is_active.is_(True))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[InvestmentTransaction]:
        statement = select(InvestmentTransaction).where(InvestmentTransaction.customer_id == customer_id)
        if active_only:
            statement = statement.where(InvestmentTransaction.is_active.is_(True))
        result = await self.db.execute(
            statement.order_by(InvestmentTransaction.transaction_date.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_advisor(
        self,
        advisor_id: UUID | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        customer_id: UUID | None = None,
        scheme_id: UUID | None = None,
        transaction_type: TransactionType | None = None,
        transaction_status: TransactionStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        active_only: bool = True,
    ) -> list[InvestmentTransaction]:
        statement = select(InvestmentTransaction)
        if active_only:
            statement = statement.where(InvestmentTransaction.is_active.is_(True))
        if advisor_id is not None:
            statement = statement.where(InvestmentTransaction.advisor_id == advisor_id)
        if customer_id is not None:
            statement = statement.where(InvestmentTransaction.customer_id == customer_id)
        if scheme_id is not None:
            statement = statement.where(InvestmentTransaction.scheme_id == scheme_id)
        if transaction_type is not None:
            statement = statement.where(InvestmentTransaction.transaction_type == transaction_type)
        if transaction_status is not None:
            statement = statement.where(InvestmentTransaction.transaction_status == transaction_status)
        if date_from is not None:
            statement = statement.where(InvestmentTransaction.transaction_date >= date_from)
        if date_to is not None:
            statement = statement.where(InvestmentTransaction.transaction_date <= date_to)
        result = await self.db.execute(
            statement.order_by(InvestmentTransaction.transaction_date.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_recent_for_advisor(
        self,
        advisor_id: UUID | None = None,
        *,
        limit: int = 10,
    ) -> list[InvestmentTransaction]:
        return await self.list_by_advisor(
            advisor_id,
            limit=limit,
            transaction_status=TransactionStatus.COMPLETED,
        )

    async def update(self, transaction: InvestmentTransaction, data: dict[str, Any]) -> InvestmentTransaction:
        for field, value in data.items():
            setattr(transaction, field, value)
        await self.db.flush()
        return transaction

    async def soft_delete(self, transaction: InvestmentTransaction) -> InvestmentTransaction:
        transaction.is_active = False
        await self.db.flush()
        return transaction

    async def calculate_customer_invested_amount(self, customer_id: UUID) -> Decimal:
        statement = select(func.coalesce(func.sum(InvestmentTransaction.amount), 0)).where(
            InvestmentTransaction.customer_id == customer_id,
            InvestmentTransaction.is_active.is_(True),
            InvestmentTransaction.transaction_status == TransactionStatus.COMPLETED,
            InvestmentTransaction.transaction_type.in_(
                [TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN]
            ),
        )
        result = await self.db.execute(statement)
        return Decimal(result.scalar_one() or 0)

    async def calculate_customer_current_units(self, customer_id: UUID) -> Decimal:
        statement = select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            InvestmentTransaction.transaction_type.in_(
                                [TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN]
                            ),
                            InvestmentTransaction.units,
                        ),
                        (
                            InvestmentTransaction.transaction_type.in_(
                                [TransactionType.SELL, TransactionType.SWITCH_OUT]
                            ),
                            -InvestmentTransaction.units,
                        ),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(
            InvestmentTransaction.customer_id == customer_id,
            InvestmentTransaction.is_active.is_(True),
            InvestmentTransaction.transaction_status == TransactionStatus.COMPLETED,
        )
        result = await self.db.execute(statement)
        return Decimal(result.scalar_one() or 0)

    async def calculate_scheme_units_for_customer(self, *, customer_id: UUID, scheme_id: UUID) -> Decimal:
        statement = select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            InvestmentTransaction.transaction_type.in_(
                                [TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN]
                            ),
                            InvestmentTransaction.units,
                        ),
                        (
                            InvestmentTransaction.transaction_type.in_(
                                [TransactionType.SELL, TransactionType.SWITCH_OUT]
                            ),
                            -InvestmentTransaction.units,
                        ),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(
            InvestmentTransaction.customer_id == customer_id,
            InvestmentTransaction.scheme_id == scheme_id,
            InvestmentTransaction.is_active.is_(True),
            InvestmentTransaction.transaction_status == TransactionStatus.COMPLETED,
        )
        result = await self.db.execute(statement)
        return Decimal(result.scalar_one() or 0)

    async def customer_transaction_summary(self, customer_id: UUID) -> dict[str, Any]:
        statement = select(
            func.count(InvestmentTransaction.id),
            func.coalesce(
                func.sum(
                    case(
                        (
                            InvestmentTransaction.transaction_type.in_(
                                [TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN]
                            ),
                            InvestmentTransaction.amount,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            InvestmentTransaction.transaction_type.in_(
                                [TransactionType.SELL, TransactionType.SWITCH_OUT]
                            ),
                            InvestmentTransaction.amount,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            InvestmentTransaction.transaction_type.in_(
                                [TransactionType.BUY, TransactionType.SIP_INSTALLMENT, TransactionType.SWITCH_IN]
                            ),
                            InvestmentTransaction.units,
                        ),
                        (
                            InvestmentTransaction.transaction_type.in_(
                                [TransactionType.SELL, TransactionType.SWITCH_OUT]
                            ),
                            -InvestmentTransaction.units,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.max(InvestmentTransaction.transaction_date),
        ).where(
            InvestmentTransaction.customer_id == customer_id,
            InvestmentTransaction.is_active.is_(True),
            InvestmentTransaction.transaction_status == TransactionStatus.COMPLETED,
        )
        result = await self.db.execute(statement)
        total_transactions, total_invested, total_sell, total_units, latest_date = result.one()
        return {
            "total_transactions": int(total_transactions or 0),
            "total_invested_amount": Decimal(total_invested or 0),
            "total_sell_amount": Decimal(total_sell or 0),
            "total_units": Decimal(total_units or 0),
            "latest_transaction_date": latest_date,
        }
