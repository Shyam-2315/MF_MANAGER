from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings
from app.exceptions import UnauthorizedException

BCRYPT_MAX_PASSWORD_BYTES = 72
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def validate_bcrypt_password(password: str) -> None:
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("Password must be 72 bytes or fewer for bcrypt")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    validate_bcrypt_password(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_token(
    *,
    subject: str,
    token_type: str,
    secret_key: str,
    expires_delta: timedelta,
    claims: dict[str, Any] | None = None,
) -> str:
    expire = datetime.now(UTC) + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "token_type": token_type,
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, secret_key, algorithm=get_settings().jwt_algorithm)


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    return create_token(
        subject=subject,
        token_type=ACCESS_TOKEN_TYPE,
        secret_key=settings.jwt_secret_key,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        claims=claims,
    )


def create_refresh_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    return create_token(
        subject=subject,
        token_type=REFRESH_TOKEN_TYPE,
        secret_key=settings.jwt_refresh_secret_key,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        claims=claims,
    )


def decode_token(token: str, *, secret_key: str, expected_token_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedException("Invalid or expired authentication token") from exc

    if payload.get("token_type") != expected_token_type:
        raise UnauthorizedException("Invalid token type")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return decode_token(token, secret_key=settings.jwt_secret_key, expected_token_type=ACCESS_TOKEN_TYPE)


def decode_refresh_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return decode_token(token, secret_key=settings.jwt_refresh_secret_key, expected_token_type=REFRESH_TOKEN_TYPE)
