"""Standard error hierarchy and exception handlers for BizPilot API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str
    code: str | None = None


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: list[ErrorDetail] | None = None
    correlation_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppException(Exception):
    """Base exception for all BizPilot domain/application errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class ValidationException(AppException):
    def __init__(
        self,
        message: str = "Invalid request payload or parameters",
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


class AuthenticationException(AppException):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            message=message,
            code=ErrorCode.AUTHENTICATION_REQUIRED,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationException(AppException):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(
            message=message,
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(
            message=message,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict or duplicate reference") -> None:
        super().__init__(
            message=message,
            code=ErrorCode.CONFLICT,
            status_code=status.HTTP_409_CONFLICT,
        )


class RateLimitException(AppException):
    def __init__(self, message: str = "Too many requests, please retry later") -> None:
        super().__init__(
            message=message,
            code=ErrorCode.RATE_LIMITED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "Service temporarily unavailable") -> None:
        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _get_correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None) or request.headers.get("x-correlation-id")


def build_error_response(
    code: ErrorCode,
    message: str,
    status_code: int,
    correlation_id: str | None = None,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    body = {
        "error": {
            "code": code.value,
            "message": message,
            "details": [d.model_dump() for d in details] if details else None,
            "correlation_id": correlation_id,
        }
    }
    return JSONResponse(status_code=status_code, content=body)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        correlation_id=_get_correlation_id(request),
        details=exc.details,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details: list[ErrorDetail] = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", []) if item != "body")
        details.append(
            ErrorDetail(
                field=loc if loc else None,
                message=err.get("msg", "Validation error"),
                code=err.get("type"),
            )
        )
    return build_error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        correlation_id=_get_correlation_id(request),
        details=details,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code_map: dict[int, ErrorCode] = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.AUTHENTICATION_REQUIRED,
        403: ErrorCode.PERMISSION_DENIED,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMITED,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_SERVER_ERROR)
    message = str(exc.detail) if exc.detail else "HTTP error"
    return build_error_response(
        code=code,
        message=message,
        status_code=exc.status_code,
        correlation_id=_get_correlation_id(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Always sanitize unhandled internal server errors
    return build_error_response(
        code=ErrorCode.INTERNAL_SERVER_ERROR,
        message="An unexpected internal server error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        correlation_id=_get_correlation_id(request),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
