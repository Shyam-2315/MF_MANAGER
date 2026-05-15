from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import ConflictException, UnauthorizedException
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginResponse, RefreshResponse
from app.schemas.user import UserCreate
from app.security import create_access_token, create_refresh_token, decode_refresh_token, get_password_hash, verify_password


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)

    async def register(self, payload: UserCreate) -> User:
        existing_user = await self.users.get_by_email(payload.email)
        if existing_user is not None:
            raise ConflictException("A user with this email already exists")

        user = await self.users.create(
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            full_name=payload.full_name,
            phone=payload.phone,
        )
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(self, email: str, password: str) -> LoginResponse:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Incorrect email or password")
        if not user.is_active:
            raise UnauthorizedException("User account is inactive")

        tokens = self._create_token_pair(user)
        return LoginResponse(**tokens, role=user.role, user=user)

    async def refresh(self, refresh_token: str) -> RefreshResponse:
        payload = decode_refresh_token(refresh_token)
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid refresh token")

        try:
            user = await self.users.get_by_id(user_id)
        except ValueError as exc:
            raise UnauthorizedException("Invalid refresh token") from exc
        if user is None:
            raise UnauthorizedException("User does not exist")
        if not user.is_active:
            raise UnauthorizedException("User account is inactive")

        tokens = self._create_token_pair(user)
        return RefreshResponse(**tokens, role=user.role)

    def _create_token_pair(self, user: User) -> dict[str, str | int]:
        settings = get_settings()
        access_token = create_access_token(
            subject=str(user.id),
            claims={"role": user.role.value},
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            claims={"role": user.role.value},
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": settings.access_token_expire_minutes * 60,
        }
