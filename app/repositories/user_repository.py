from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: UUID | str) -> User | None:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        result = await self.db.execute(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str | None = None,
        phone: str | None = None,
        role: UserRole = UserRole.CUSTOMER,
        is_active: bool = True,
        is_verified: bool = False,
    ) -> User:
        user = User(
            email=email.lower(),
            password_hash=password_hash,
            full_name=full_name,
            phone=phone,
            role=role,
            is_active=is_active,
            is_verified=is_verified,
        )
        self.db.add(user)
        await self.db.flush()
        return user
