"""AI module package for BizPilot AI Assistant."""

from app.modules.ai.exceptions import (
    AIConfigurationException,
    AIDisabledException,
    AIException,
    AIPermissionDeniedException,
    AIProviderUnavailableException,
    AITimeoutException,
)
from app.modules.ai.provider import AIProviderAdapter, get_ai_provider
from app.modules.ai.tools import OPENAI_TOOL_DEFINITIONS, AIToolRegistry

__all__ = [
    "AIConfigurationException",
    "AIDisabledException",
    "AIException",
    "AIPermissionDeniedException",
    "AIProviderUnavailableException",
    "AITimeoutException",
    "AIProviderAdapter",
    "get_ai_provider",
    "OPENAI_TOOL_DEFINITIONS",
    "AIToolRegistry",
]
