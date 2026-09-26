"""Provider-neutral contracts. No prompt/output persistence or provider-shaped API."""

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

CAPABILITIES = ("text.generate", "reasoning.generate", "code.generate")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


class InferenceRequest(StrictModel):
    model_id: str = Field(min_length=1, max_length=128)
    input: str = Field(min_length=1, max_length=262144)
    instruction: str = Field(default="", max_length=262144)
    capability_id: Literal["text.generate", "reasoning.generate", "code.generate"] = "text.generate"
    max_output_tokens: int = Field(default=1024, ge=1, le=32768)
    temperature: float = Field(default=0.7, ge=0, le=2, allow_inf_nan=False)
    timeout_seconds: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)


class Usage(StrictModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ProviderResult(StrictModel):
    text: str
    finish_reason: Literal["stop", "length"]
    usage: Usage | None = None


ERROR_MESSAGES = {
    "invalid_request": "Request does not satisfy the documented schema or limits.",
    "unknown_model": "Model ID is not configured.",
    "unknown_capability": "Capability ID is not supported.",
    "context_limit": "Input and output budget exceed the configured context allowance.",
    "busy": "Inference capacity is in use; no work was queued.",
    "provider_unavailable": "The configured provider is unavailable.",
    "provider_timeout": "The provider operation exceeded its deadline.",
    "provider_rejected": "The provider rejected the request.",
    "provider_unauthorized": "Provider authentication failed.",
    "provider_busy": "The provider is busy or rate limited.",
    "invalid_provider_response": "The provider returned an invalid response.",
    "response_limit": "The provider response exceeded the configured size limit.",
    "internal_error": "The intelligence operation failed.",
}


class IntelligenceError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(ERROR_MESSAGES[code])

    def public(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class Provider(Protocol):
    async def health(self) -> None: ...
    async def infer(self, request: InferenceRequest, provider_model: str) -> ProviderResult: ...
    async def close(self) -> None: ...
