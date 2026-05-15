from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(TokenPair):
    role: UserRole
    user: UserRead


class RefreshResponse(TokenPair):
    role: UserRole
