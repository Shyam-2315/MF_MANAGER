from http import HTTPStatus
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.utils.context import get_request_id


class AppException(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "internal_error"
    message = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        self.error_code = error_code or self.error_code
        self.details = details
        super().__init__(self.message)


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"
    message = "Resource not found"


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"
    message = "Authentication failed"


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"
    message = "Forbidden"


class BadRequestException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "bad_request"
    message = "Bad request"


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"
    message = "Resource conflict"


def error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
            "request_id": get_request_id(),
        }
    }
    if details is not None:
        content["error"]["details"] = jsonable_encoder(details)
    headers = {"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
    return JSONResponse(status_code=status_code, content=content, headers=headers)


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="validation_error",
        message="Request validation failed",
        details=exc.errors(),
    )


async def database_exception_handler(_: Request, __: SQLAlchemyError) -> JSONResponse:
    return error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_code="database_error",
        message="Database operation failed",
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return error_response(
        status_code=status_code,
        error_code="internal_error",
        message=HTTPStatus(status_code).phrase,
    )
