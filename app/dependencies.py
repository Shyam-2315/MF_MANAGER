from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.exceptions import ForbiddenException, UnauthorizedException
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.security import decode_access_token

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/token")

DbSession = Annotated[AsyncSession, Depends(get_db)]
Token = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(token: Token, db: DbSession) -> User:
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Invalid authentication token")

    try:
        user_uuid = UUID(str(user_id))
    except ValueError as exc:
        raise UnauthorizedException("Invalid authentication token") from exc

    user = await UserRepository(db).get_by_id(user_uuid)
    if user is None:
        raise UnauthorizedException("User does not exist")
    if not user.is_active:
        raise UnauthorizedException("User account is inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class RoleChecker:
    def __init__(self, *allowed_roles: UserRole) -> None:
        self.allowed_roles = set(allowed_roles)

    def __call__(self, current_user: CurrentUser) -> User:
        if current_user.role not in self.allowed_roles:
            raise ForbiddenException("Insufficient permissions")
        return current_user
