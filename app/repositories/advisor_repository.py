from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.advisor import Advisor


class AdvisorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_user_id(self, user_id: UUID) -> Advisor | None:
        result = await self.db.execute(select(Advisor).where(Advisor.user_id == user_id))
        return result.scalar_one_or_none()

    async def create(self, *, user_id: UUID, data: dict[str, Any]) -> Advisor:
        advisor = Advisor(user_id=user_id, **data)
        self.db.add(advisor)
        await self.db.flush()
        return advisor

    async def update(self, advisor: Advisor, data: dict[str, Any]) -> Advisor:
        for field, value in data.items():
            setattr(advisor, field, value)
        await self.db.flush()
        return advisor

    async def count_customers(self, advisor_id: UUID | None = None) -> int:
        if await self._table_exists("customers"):
            return await self._count_rows("customers", advisor_id=advisor_id)
        if advisor_id is None:
            result = await self.db.execute(text("SELECT COUNT(*) FROM users WHERE role = 'CUSTOMER'"))
            return int(result.scalar_one() or 0)
        return 0

    async def sum_total_aum(self, advisor_id: UUID | None = None) -> Decimal:
        for table_name, amount_column in (
            ("customer_portfolios", "current_value"),
            ("portfolios", "current_value"),
            ("investments", "current_value"),
        ):
            if await self._table_exists(table_name) and await self._column_exists(table_name, amount_column):
                return await self._sum_numeric(table_name, amount_column, advisor_id=advisor_id)
        return Decimal("0")

    async def sum_monthly_sip_amount(self, advisor_id: UUID | None = None) -> Decimal:
        if not await self._table_exists("sips"):
            return Decimal("0")
        if not await self._column_exists("sips", "amount"):
            return Decimal("0")
        return await self._sum_numeric("sips", "amount", advisor_id=advisor_id, active_only=True)

    async def count_pending_kyc_customers(self, advisor_id: UUID | None = None) -> int:
        if not await self._table_exists("customers"):
            return 0
        if not await self._column_exists("customers", "kyc_status"):
            return 0
        if advisor_id is not None and not await self._column_exists("customers", "advisor_id"):
            return 0

        where_clauses = ["kyc_status IN ('PENDING', 'IN_PROGRESS', 'UNDER_REVIEW')"]
        params: dict[str, Any] = {}
        if advisor_id is not None and await self._column_exists("customers", "advisor_id"):
            where_clauses.append("advisor_id = :advisor_id")
            params["advisor_id"] = advisor_id

        result = await self.db.execute(
            text(f"SELECT COUNT(*) FROM customers WHERE {' AND '.join(where_clauses)}"),
            params,
        )
        return int(result.scalar_one() or 0)

    async def count_active_sips(self, advisor_id: UUID | None = None) -> int:
        if not await self._table_exists("sips"):
            return 0
        if advisor_id is not None and not await self._column_exists("sips", "advisor_id"):
            return 0

        where_clauses: list[str] = []
        params: dict[str, Any] = {}
        if await self._column_exists("sips", "status"):
            where_clauses.append("status = 'ACTIVE'")
        if advisor_id is not None and await self._column_exists("sips", "advisor_id"):
            where_clauses.append("advisor_id = :advisor_id")
            params["advisor_id"] = advisor_id

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        result = await self.db.execute(text(f"SELECT COUNT(*) FROM sips{where_sql}"), params)
        return int(result.scalar_one() or 0)

    async def list_recent_transactions(self, advisor_id: UUID | None = None, *, limit: int = 10) -> list[dict[str, Any]]:
        if not await self._table_exists("transactions"):
            return []
        if advisor_id is not None and not await self._column_exists("transactions", "advisor_id"):
            return []

        columns = await self._existing_columns(
            "transactions",
            ("id", "customer_id", "transaction_type", "type", "amount", "status", "transaction_date", "created_at"),
        )
        if "id" not in columns:
            return []

        transaction_type_column = "transaction_type" if "transaction_type" in columns else "type"
        date_column = "transaction_date" if "transaction_date" in columns else "created_at"
        select_columns = [
            "id",
            "customer_id" if "customer_id" in columns else "NULL AS customer_id",
            f"{transaction_type_column} AS transaction_type" if transaction_type_column in columns else "NULL AS transaction_type",
            "amount" if "amount" in columns else "0 AS amount",
            "status" if "status" in columns else "NULL AS status",
            f"{date_column} AS transaction_date" if date_column in columns else "NULL AS transaction_date",
        ]

        where_clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if advisor_id is not None and await self._column_exists("transactions", "advisor_id"):
            where_clauses.append("advisor_id = :advisor_id")
            params["advisor_id"] = advisor_id

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        order_sql = f" ORDER BY {date_column} DESC" if date_column in columns else ""
        result = await self.db.execute(
            text(f"SELECT {', '.join(select_columns)} FROM transactions{where_sql}{order_sql} LIMIT :limit"),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def _table_exists(self, table_name: str) -> bool:
        result = await self.db.execute(text("SELECT to_regclass(:table_name) IS NOT NULL"), {"table_name": table_name})
        return bool(result.scalar_one())

    async def _column_exists(self, table_name: str, column_name: str) -> bool:
        result = await self.db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                      AND column_name = :column_name
                )
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        )
        return bool(result.scalar_one())

    async def _existing_columns(self, table_name: str, column_names: tuple[str, ...]) -> set[str]:
        existing_columns: set[str] = set()
        for column_name in column_names:
            if await self._column_exists(table_name, column_name):
                existing_columns.add(column_name)
        return existing_columns

    async def _count_rows(self, table_name: str, advisor_id: UUID | None = None) -> int:
        params: dict[str, Any] = {}
        where_sql = ""
        if advisor_id is not None:
            if not await self._column_exists(table_name, "advisor_id"):
                return 0
            where_sql = " WHERE advisor_id = :advisor_id"
            params["advisor_id"] = advisor_id
        result = await self.db.execute(text(f"SELECT COUNT(*) FROM {table_name}{where_sql}"), params)
        return int(result.scalar_one() or 0)

    async def _sum_numeric(
        self,
        table_name: str,
        amount_column: str,
        advisor_id: UUID | None = None,
        *,
        active_only: bool = False,
    ) -> Decimal:
        where_clauses: list[str] = []
        params: dict[str, Any] = {}
        if advisor_id is not None:
            if not await self._column_exists(table_name, "advisor_id"):
                return Decimal("0")
            where_clauses.append("advisor_id = :advisor_id")
            params["advisor_id"] = advisor_id
        if active_only and await self._column_exists(table_name, "status"):
            where_clauses.append("status = 'ACTIVE'")

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        result = await self.db.execute(
            text(f"SELECT COALESCE(SUM({amount_column}), 0) FROM {table_name}{where_sql}"),
            params,
        )
        return Decimal(result.scalar_one() or 0)
