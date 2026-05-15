from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole
from app.security import validate_bcrypt_password


class UserBase(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, min_length=7, max_length=32, pattern=r"^\+?[0-9][0-9 .-]{6,31}$")


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_password_for_bcrypt(cls, value: str) -> str:
        validate_bcrypt_password(value)
        return value


class UserAdminCreate(UserCreate):
    role: UserRole = UserRole.CUSTOMER
    is_active: bool = True
    is_verified: bool = False


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, min_length=7, max_length=32, pattern=r"^\+?[0-9][0-9 .-]{6,31}$")
    is_active: bool | None = None
    is_verified: bool | None = None
    role: UserRole | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
