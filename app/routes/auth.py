from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.auth import LoginRequest, LoginResponse, RefreshResponse, RefreshTokenRequest
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> UserRead:
    return await AuthService(db).register(payload)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> LoginResponse:
    return await AuthService(db).login(str(payload.email), payload.password)


@router.post("/token", response_model=LoginResponse)
async def token_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    return await AuthService(db).login(form_data.username, form_data.password)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RefreshResponse:
    return await AuthService(db).refresh(payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: CurrentUser) -> UserRead:
    return current_user
