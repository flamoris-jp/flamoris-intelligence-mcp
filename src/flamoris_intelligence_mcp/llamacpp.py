"""The only module that knows llama.cpp's HTTP/OpenAI-compatible wire format."""

import asyncio
import json

import httpx
from pydantic import ValidationError

from .config import Settings
from .contracts import InferenceRequest, IntelligenceError, ProviderResult, Usage


class LlamaCppProvider:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
        if settings.provider_api_key:
            headers["Authorization"] = "Bearer " + settings.provider_api_key.get_secret_value()
        self.client = httpx.AsyncClient(
            base_url=settings.provider_url + "/",
            headers=headers,
            timeout=settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            limits=httpx.Limits(max_connections=settings.max_concurrency + 1),
        )

    async def close(self):
        await self.client.aclose()

    async def _json(self, method: str, path: str, timeout: float, payload=None):
        try:
            async with asyncio.timeout(timeout):
                async with self.client.stream(method, path, json=payload) as response:
                    status = response.status_code
                    if status in (401, 403):
                        raise IntelligenceError("provider_unauthorized")
                    if status == 429:
                        raise IntelligenceError("provider_busy")
                    if status >= 500:
                        raise IntelligenceError("provider_unavailable")
                    if status != 200:
                        raise IntelligenceError("provider_rejected")
                    # Avoid decompression bombs. The request explicitly asks for identity encoding.
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise IntelligenceError("invalid_provider_response")
                    size = response.headers.get("content-length")
                    if size is not None:
                        try:
                            length = int(size)
                        except ValueError:
                            raise IntelligenceError("invalid_provider_response") from None
                        if length < 0:
                            raise IntelligenceError("invalid_provider_response")
                        if length > self.settings.max_response_bytes:
                            raise IntelligenceError("response_limit")
                    data = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=16384):
                        if len(data) + len(chunk) > self.settings.max_response_bytes:
                            raise IntelligenceError("response_limit")
                        data.extend(chunk)
                    try:
                        result = json.loads(data)
                    except (ValueError, UnicodeError, RecursionError):
                        raise IntelligenceError("invalid_provider_response") from None
                    if not isinstance(result, dict):
                        raise IntelligenceError("invalid_provider_response")
                    return result
        except (TimeoutError, httpx.TimeoutException):
            raise IntelligenceError("provider_timeout") from None
        except httpx.HTTPError:
            raise IntelligenceError("provider_unavailable") from None

    async def health(self):
        result = await self._json("GET", "health", self.settings.health_timeout_seconds)
        if result.get("status") != "ok":
            raise IntelligenceError("provider_unavailable")

    async def infer(self, request: InferenceRequest, provider_model: str) -> ProviderResult:
        messages = []
        if request.instruction:
            messages.append({"role": "system", "content": request.instruction})
        messages.append({"role": "user", "content": request.input})
        result = await self._json(
            "POST",
            "v1/chat/completions",
            request.timeout_seconds or self.settings.timeout_seconds,
            {
                "model": provider_model,
                "messages": messages,
                "max_tokens": request.max_output_tokens,
                "temperature": request.temperature,
                "stream": False,
                "n": 1,
            },
        )
        try:
            choices = result["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            message = choice["message"]
            if message.get("role") != "assistant" or message.get("tool_calls"):
                raise ValueError
            text = message["content"]
            if not isinstance(text, str):
                raise ValueError
            if len(text.encode("utf-8")) > self.settings.max_output_bytes:
                raise IntelligenceError("response_limit")
            usage = None
            if result.get("usage") is not None:
                raw = result["usage"]
                usage = Usage(
                    input_tokens=raw["prompt_tokens"],
                    output_tokens=raw["completion_tokens"],
                    total_tokens=raw["total_tokens"],
                )
                if (
                    usage.input_tokens + usage.output_tokens != usage.total_tokens
                    or usage.output_tokens > request.max_output_tokens
                ):
                    raise ValueError
            return ProviderResult(text=text, finish_reason=choice["finish_reason"], usage=usage)
        except (KeyError, TypeError, ValueError, AttributeError, ValidationError, UnicodeError):
            raise IntelligenceError("invalid_provider_response") from None
