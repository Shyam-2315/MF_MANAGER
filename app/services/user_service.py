from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserAdminCreate, UserUpdate
from app.security import get_password_hash


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)

    async def list_users(self, *, limit: int = 100, offset: int = 0):
        return await self.users.list(limit=limit, offset=offset)

    async def get_user(self, user_id: UUID):
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found")
        return user

    async def create_user(self, payload: UserAdminCreate):
        existing_user = await self.users.get_by_email(payload.email)
        if existing_user is not None:
            raise ConflictException("A user with this email already exists")

        user = await self.users.create(
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            full_name=payload.full_name,
            phone=payload.phone,
            role=payload.role,
            is_active=payload.is_active,
            is_verified=payload.is_verified,
        )
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user(self, user_id: UUID, payload: UserUpdate):
        user = await self.get_user(user_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user
