"""One request authority shared by both transports; no jobs or durable state."""

import asyncio
import time
import uuid

from pydantic import ValidationError

from . import __version__
from .config import Settings
from .contracts import CAPABILITIES, InferenceRequest, IntelligenceError, Provider


class IntelligenceService:
    def __init__(self, settings: Settings, provider: Provider):
        self.settings = settings
        self.provider = provider
        self.models = {model.id: model for model in settings.models}
        self.active = 0
        self.health_active = False

    def model(self, model_id: str):
        if model_id not in self.models:
            raise IntelligenceError("unknown_model")
        model = self.models[model_id]
        return {
            "model_id": model.id,
            "provider_id": "llamacpp",
            "capability_ids": list(CAPABILITIES),
            "context_tokens": model.context_tokens,
            "max_output_tokens": model.max_output_tokens,
            "discovery": "configured",
        }

    def capability(self, capability_id: str):
        if capability_id not in CAPABILITIES:
            raise IntelligenceError("unknown_capability")
        return {
            "capability_id": capability_id,
            "model_ids": list(self.models),
            "tool": "inference.execute",
            "execution": "synchronous",
        }

    async def health(self):
        provider = {"provider_id": "llamacpp", "available": False}
        if self.health_active:
            provider["error"] = IntelligenceError("busy").public()
        else:
            self.health_active = True
            try:
                async with asyncio.timeout(self.settings.health_timeout_seconds):
                    await self.provider.health()
                provider["available"] = True
            except TimeoutError:
                provider["error"] = IntelligenceError("provider_timeout").public()
            except IntelligenceError as exc:
                provider["error"] = exc.public()
            finally:
                self.health_active = False
        return {
            "healthy": True,
            "version": __version__,
            "active_requests": self.active,
            "providers": [provider],
        }

    def validate(self, raw: dict) -> InferenceRequest:
        try:
            request = InferenceRequest.model_validate(raw)
            byte_count = len(request.input.encode("utf-8")) + len(
                request.instruction.encode("utf-8")
            )
            if not request.input.strip() or byte_count > self.settings.max_input_bytes:
                raise ValueError
            if request.timeout_seconds and request.timeout_seconds > self.settings.timeout_seconds:
                raise ValueError
        except (ValueError, TypeError, ValidationError, UnicodeError):
            raise IntelligenceError("invalid_request") from None
        self.model(request.model_id)
        model = self.models[request.model_id]
        if request.max_output_tokens > model.max_output_tokens:
            raise IntelligenceError("invalid_request")
        # Deliberately conservative admission estimate, not a model tokenizer claim.
        # Provider remains responsible for exact chat-template/token context validation.
        if byte_count + 512 + request.max_output_tokens > model.context_tokens:
            raise IntelligenceError("context_limit")
        return request

    async def execute(self, raw: dict):
        execution_id = str(uuid.uuid4())
        started = time.monotonic()
        try:
            request = self.validate(raw)
            # No await between test/reservation; all tools share one event loop.
            if self.active >= self.settings.max_concurrency:
                raise IntelligenceError("busy")
            self.active += 1
            try:
                async with asyncio.timeout(
                    request.timeout_seconds or self.settings.timeout_seconds
                ):
                    result = await self.provider.infer(
                        request, self.models[request.model_id].provider_model
                    )
            except TimeoutError:
                raise IntelligenceError("provider_timeout") from None
            finally:
                self.active -= 1
            return {
                "ok": True,
                "execution_id": execution_id,
                "provider_id": "llamacpp",
                "model_id": request.model_id,
                "capability_id": request.capability_id,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                **result.model_dump(),
            }
        except IntelligenceError as exc:
            return {"ok": False, "execution_id": execution_id, "error": exc.public()}
        except Exception:
            # Provider exceptions may contain private URLs or data. Cancellation propagates.
            return {
                "ok": False,
                "execution_id": execution_id,
                "error": IntelligenceError("internal_error").public(),
            }
