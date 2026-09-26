"""AI module package for BizPilot AI Assistant."""

from app.modules.ai.assistant import (
    BizPilotAssistantOrchestrator,
    build_sdk_function_tools,
    build_system_message,
)
from app.modules.ai.exceptions import (
    AIConfigurationException,
    AIDisabledException,
    AIException,
    AIPermissionDeniedException,
    AIProviderUnavailableException,
    AITimeoutException,
)
from app.modules.ai.metadata_service import AIMetadataService
from app.modules.ai.models import AIInteraction, AIToolCall
from app.modules.ai.provider import AIProviderAdapter, get_ai_provider
from app.modules.ai.redaction import redact_dict, redact_sensitive_text
from app.modules.ai.router import ai_router
from app.modules.ai.schemas import (
    AIInteractionMetadataRecord,
    AIToolCallMetadataRecord,
)
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
    "BizPilotAssistantOrchestrator",
    "build_sdk_function_tools",
    "build_system_message",
    "AIInteraction",
    "AIToolCall",
    "AIMetadataService",
    "redact_sensitive_text",
    "redact_dict",
    "AIInteractionMetadataRecord",
    "AIToolCallMetadataRecord",
    "ai_router",
]
