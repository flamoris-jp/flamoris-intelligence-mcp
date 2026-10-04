"""Bounded stateless provider adapters; no MCP imports, servers or durable state."""

import httpx

from ._version import __version__
from .config import ModelEntry, Settings
from .contracts import IntelligenceError
from .llamacpp import LlamaCppProvider
from .openai_provider import OpenAIProvider
from .service import IntelligenceService

__all__ = [
    "IntelligenceError",
    "IntelligenceService",
    "ModelEntry",
    "Settings",
    "create_service",
    "__version__",
]


def create_service(settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
    providers = {}
    if any(m.provider_id == "llamacpp" for m in settings.models):
        providers["llamacpp"] = LlamaCppProvider(settings, transport)
    if any(m.provider_id == "openai" for m in settings.models):
        providers["openai"] = OpenAIProvider(settings, transport)
    return IntelligenceService(settings, providers)
