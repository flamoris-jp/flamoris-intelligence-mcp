"""Explicit stateless OpenAI Responses adapter; credentials stay in Intelligence."""

from decimal import Decimal

import httpx

from .contracts import IntelligenceError, ProviderResult, Usage
from .llamacpp import LlamaCppProvider


class OpenAIProvider(LlamaCppProvider):
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1/",
            headers={
                "Authorization": "Bearer " + settings.openai_api_key.get_secret_value(),
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            timeout=settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=transport or httpx.AsyncHTTPTransport(retries=0),
            limits=httpx.Limits(max_connections=settings.max_concurrency + 1),
        )

    async def health(self):
        # A free authenticated reachability probe, never an inference or model activation.
        result = await self._json("GET", "models", self.settings.health_timeout_seconds)
        if result.get("object") != "list" or type(result.get("data")) is not list:
            raise IntelligenceError("provider_unavailable")

    async def health_model(self, provider_model):
        from urllib.parse import quote

        result = await self._json(
            "GET", "models/" + quote(provider_model, safe=""), self.settings.health_timeout_seconds
        )
        if result.get("object") != "model" or result.get("id") != provider_model:
            raise IntelligenceError("provider_unavailable")

    def cost_ceiling(self, request):
        # UTF-8 bytes + template allowance is a conservative input token bound.
        tokens = len(request.input.encode()) + len(request.instruction.encode()) + 512
        estimated = (
            Decimal(tokens) * Decimal(str(self.settings.openai_input_usd_per_million))
            + Decimal(request.max_output_tokens)
            * Decimal(str(self.settings.openai_output_usd_per_million))
        ) / Decimal(1000000)
        if estimated > Decimal(str(self.settings.openai_max_request_usd)):
            raise IntelligenceError("context_limit")

    async def infer(self, request, provider_model):
        self.cost_ceiling(request)
        # Temperature omitted: not every Responses model accepts sampling controls.
        # No provider conversation/history IDs, background jobs or tool calls.
        result = await self._json(
            "POST",
            "responses",
            request.timeout_seconds or self.settings.timeout_seconds,
            {
                "model": provider_model,
                "input": request.input,
                "instructions": request.instruction,
                "max_output_tokens": request.max_output_tokens,
                "store": False,
                "stream": False,
                "background": False,
                "tools": [],
                "truncation": "disabled",
            },
        )
        try:
            if result.get("model") != provider_model:
                raise ValueError()
            status = result["status"]
            if status not in {"completed", "incomplete"} or result.get("error") is not None:
                raise ValueError()
            if (
                status == "incomplete"
                and result.get("incomplete_details", {}).get("reason") != "max_output_tokens"
            ):
                raise ValueError()
            output = result["output"]
            if type(output) is not list or len(output) > 64:
                raise ValueError()
            parts = []
            for item in output:
                if item.get("type") == "reasoning":
                    continue
                if item.get("type") != "message" or item.get("role") != "assistant":
                    raise ValueError()
                for content in item["content"]:
                    if content.get("type") != "output_text" or type(content.get("text")) is not str:
                        raise ValueError()
                    parts.append(content["text"])
            text = "\n".join(parts)
            if not text.strip() or len(text.encode()) > self.settings.max_output_bytes:
                raise IntelligenceError("response_limit")
            raw = result["usage"]
            usage = Usage(**{k: raw[k] for k in ("input_tokens", "output_tokens", "total_tokens")})
            if (
                usage.input_tokens + usage.output_tokens != usage.total_tokens
                or usage.output_tokens > request.max_output_tokens
            ):
                raise ValueError()
            return ProviderResult(
                text=text, finish_reason="stop" if status == "completed" else "length", usage=usage
            )
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
            raise IntelligenceError("invalid_provider_response") from None
