"""One bounded stateless provider boundary; no protocol, jobs or durable state."""

import asyncio
import time
import uuid
from decimal import Decimal

from pydantic import ValidationError

from ._version import __version__
from .config import Settings
from .contracts import (
    CAPABILITIES,
    InferenceRequest,
    IntelligenceError,
    MessageInferenceRequest,
    Provider,
)


class IntelligenceService:
    def __init__(self, settings: Settings, provider: Provider):
        self.settings = settings
        self.provider = provider
        self.providers = provider if isinstance(provider, dict) else {"llamacpp": provider}
        self.active_by_provider = {name: 0 for name in self.providers}
        self.models = {model.id: model for model in settings.models}
        self.active = 0
        self.health_active = False

    def model(self, model_id: str):
        if model_id not in self.models:
            raise IntelligenceError("unknown_model")
        model = self.models[model_id]
        return {
            "model_id": model.id,
            "provider_id": model.provider_id,
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
            "execution": "synchronous",
        }

    async def close(self):
        for provider in self.providers.values():
            await provider.close()

    async def model_available(self, model_id: str):
        descriptor = self.model(model_id)
        model = self.models[model_id]
        if model.provider_id not in self.providers:
            raise IntelligenceError("provider_unavailable")
        if self.health_active:
            raise IntelligenceError("busy")
        self.health_active = True
        try:
            async with asyncio.timeout(self.settings.health_timeout_seconds):
                await self.providers[model.provider_id].health_model(model.provider_model)
        except TimeoutError:
            raise IntelligenceError("provider_timeout") from None
        except IntelligenceError:
            raise
        except Exception:
            raise IntelligenceError("provider_unavailable") from None
        finally:
            self.health_active = False
        return {**descriptor, "available": True}

    async def health(self):
        async def probe(name, adapter):
            value = {"provider_id": name, "available": False}
            try:
                async with asyncio.timeout(self.settings.health_timeout_seconds):
                    await adapter.health()
                value["available"] = True
            except TimeoutError:
                value["error"] = IntelligenceError("provider_timeout").public()
            except IntelligenceError as exc:
                value["error"] = exc.public()
            except Exception:
                value["error"] = IntelligenceError("provider_unavailable").public()
            return value

        if self.health_active:
            providers = [
                {
                    "provider_id": name,
                    "available": False,
                    "error": IntelligenceError("busy").public(),
                }
                for name in self.providers
            ]
        else:
            self.health_active = True
            try:
                providers = await asyncio.gather(*(probe(n, p) for n, p in self.providers.items()))
            finally:
                self.health_active = False
        return {
            "healthy": True,
            "version": __version__,
            "active_requests": self.active,
            "providers": providers,
        }

    def validate(self, raw: dict) -> InferenceRequest:
        return self._validate(raw, InferenceRequest)

    def validate_messages(self, raw: dict) -> MessageInferenceRequest:
        return self._validate(raw, MessageInferenceRequest)

    def _validate(self, raw: dict, schema):
        try:
            request = schema.model_validate(raw)
            byte_count = request.input_bytes()
            nonempty = (
                any(message.content.strip() for message in request.messages)
                if isinstance(request, MessageInferenceRequest)
                else request.input.strip()
            )
            if not nonempty or byte_count > self.settings.max_input_bytes:
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
        overhead = 32 * len(request.messages) if isinstance(request, MessageInferenceRequest) else 0
        if byte_count + overhead + 512 + request.max_output_tokens > model.context_tokens:
            raise IntelligenceError("context_limit")
        return request

    async def execute(self, raw: dict):
        return await self._execute(raw, self.validate)

    async def execute_messages(self, raw: dict):
        return await self._execute(raw, self.validate_messages)

    async def _execute(self, raw: dict, validate):
        execution_id = str(uuid.uuid4())
        started = time.monotonic()
        try:
            request = validate(raw)
            # No await between test/reservation; all tools share one event loop.
            provider_id = self.models[request.model_id].provider_id
            if provider_id not in self.providers:
                raise IntelligenceError("provider_unavailable")
            if self.active_by_provider[provider_id] >= self.settings.max_concurrency:
                raise IntelligenceError("busy")
            self.active += 1
            self.active_by_provider[provider_id] += 1
            try:
                async with asyncio.timeout(
                    request.timeout_seconds or self.settings.timeout_seconds
                ):
                    result = await self.providers[provider_id].infer(
                        request, self.models[request.model_id].provider_model
                    )
            except TimeoutError:
                raise IntelligenceError("provider_timeout") from None
            finally:
                self.active -= 1
                self.active_by_provider[provider_id] -= 1
            cost = {}
            if provider_id == "openai" and result.usage is not None:
                estimated = (
                    Decimal(result.usage.input_tokens)
                    * Decimal(str(self.settings.openai_input_usd_per_million))
                    + Decimal(result.usage.output_tokens)
                    * Decimal(str(self.settings.openai_output_usd_per_million))
                ) / Decimal(1000000)
                cost["estimated_cost_usd"] = str(estimated)
            return {
                "ok": True,
                "execution_id": execution_id,
                "provider_id": provider_id,
                "model_id": request.model_id,
                "capability_id": request.capability_id,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                **result.model_dump(),
                **cost,
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
