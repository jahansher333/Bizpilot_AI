"""Typed exception hierarchy for BizPilot AI Assistant."""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppException, ErrorCode


class AIException(AppException):
    """Base exception for all AI domain errors."""

    def __init__(
        self,
        message: str = "An AI error occurred",
        code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code)


class AIDisabledException(AIException):
    """Raised when the AI feature is disabled in settings or for the environment."""

    def __init__(
        self, message: str = "BizPilot AI Assistant is currently disabled in this environment."
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class AIConfigurationException(AIException):
    """Raised when AI settings are missing or invalid."""

    def __init__(self, message: str = "AI Assistant configuration is invalid or missing.") -> None:
        super().__init__(
            message=message,
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class AIProviderUnavailableException(AIException):
    """Raised when the upstream AI provider (OpenAI) is unreachable or returning errors."""

    def __init__(
        self,
        message: str = "The AI service is temporarily unavailable. Core operations are unaffected.",
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class AITimeoutException(AIException):
    """Raised when an AI provider call times out."""

    def __init__(
        self,
        message: str = "The AI request timed out. Please try again with a more specific query.",
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )


class AIPermissionDeniedException(AIException):
    """Raised when the user does not have permission to invoke the AI Assistant."""

    def __init__(
        self, message: str = "You do not have permission to use the BizPilot AI Assistant."
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_403_FORBIDDEN,
        )
