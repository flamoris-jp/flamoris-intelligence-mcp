import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from flamoris_intelligence_mcp.config import ModelEntry, Settings
from flamoris_intelligence_mcp.contracts import InferenceRequest, IntelligenceError, ProviderResult
from flamoris_intelligence_mcp.llamacpp import LlamaCppProvider
from flamoris_intelligence_mcp.service import IntelligenceService


def response(text="result", **extra):
    return {
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        **extra,
    }


def request(**extra):
    return {"model_id": "gpt-oss-20b", "input": "hello", **extra}


class FakeProvider:
    def __init__(self):
        self.calls = []

    async def health(self):
        pass

    async def infer(self, req, model):
        self.calls.append((req, model))
        return ProviderResult(text="done", finish_reason="stop")

    async def close(self):
        pass


@pytest.mark.parametrize(
    "extra,code",
    [
        ({"input": ""}, "invalid_request"),
        ({"input": "  "}, "invalid_request"),
        ({"input": "\ud800"}, "invalid_request"),
        ({"input": "x" * 65537}, "invalid_request"),
        ({"input": "あ" * 22000}, "invalid_request"),
        ({"input": "x" * 32000}, "context_limit"),
        ({"max_output_tokens": True}, "invalid_request"),
        ({"max_output_tokens": 0}, "invalid_request"),
        ({"max_output_tokens": 4097}, "invalid_request"),
        ({"temperature": float("nan")}, "invalid_request"),
        ({"temperature": 3}, "invalid_request"),
        ({"timeout_seconds": 121}, "invalid_request"),
        ({"timeout_seconds": 0}, "invalid_request"),
        ({"model_id": "../../weights"}, "unknown_model"),
        ({"capability_id": "agent.ask"}, "invalid_request"),
        ({"url": "http://evil.example"}, "invalid_request"),
        ({"tools": []}, "invalid_request"),
    ],
)
async def test_rejection_before_provider(extra, code):
    provider = FakeProvider()
    service = IntelligenceService(Settings(), provider)
    result = await service.execute(request(**extra))
    assert result["error"]["code"] == code
    assert provider.calls == []
    assert service.active == 0


async def test_normalization_and_no_retained_context():
    provider = FakeProvider()
    settings = Settings(models=(ModelEntry(id="gpt-oss-20b", provider_model="served-alias"),))
    service = IntelligenceService(settings, provider)
    result = await service.execute(
        request(instruction="explicit policy", capability_id="code.generate")
    )
    assert result["ok"] is True
    assert result["provider_id"] == "llamacpp"
    assert result["model_id"] == "gpt-oss-20b"
    assert result["capability_id"] == "code.generate"
    assert result["text"] == "done"
    assert result["usage"] is None
    assert provider.calls[0][1] == "served-alias"
    assert provider.calls[0][0].instruction == "explicit policy"
    assert set(vars(service)) == {"settings", "provider", "models", "active", "health_active"}
    assert "provider_model" not in service.model("gpt-oss-20b")


async def test_busy_cancellation_and_capacity_release():
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class WaitingProvider(FakeProvider):
        async def infer(self, req, model):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    service = IntelligenceService(Settings(), WaitingProvider())
    running = asyncio.create_task(service.execute(request()))
    await entered.wait()
    assert (await service.execute(request()))["error"]["code"] == "busy"
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert cancelled.is_set()
    assert service.active == 0
    service.provider = FakeProvider()
    assert (await service.execute(request()))["ok"]


async def test_service_deadline_and_exception_sanitization():
    class Slow(FakeProvider):
        async def infer(self, req, model):
            await asyncio.Event().wait()

    service = IntelligenceService(Settings(timeout_seconds=0.01), Slow())
    assert (await service.execute(request()))["error"]["code"] == "provider_timeout"
    assert service.active == 0

    class Broken(FakeProvider):
        async def infer(self, req, model):
            raise RuntimeError("private prompt and secret credential")

    service.provider = Broken()
    result = await service.execute(request())
    assert result["error"]["code"] == "internal_error"
    assert "private" not in json.dumps(result)
    assert service.active == 0


async def test_adapter_wire_contract_and_usage():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            200,
            json=response(usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}),
        )

    provider = LlamaCppProvider(
        Settings(provider_url="http://localhost:8081/prefix"), httpx.MockTransport(handler)
    )
    try:
        result = await provider.infer(InferenceRequest(**request(instruction="policy")), "alias")
    finally:
        await provider.close()
    assert len(calls) == 1
    assert calls[0].url.path == "/prefix/v1/chat/completions"
    payload = json.loads(calls[0].content)
    assert payload == {
        "model": "alias",
        "messages": [{"role": "system", "content": "policy"}, {"role": "user", "content": "hello"}],
        "max_tokens": 1024,
        "temperature": 0.7,
        "stream": False,
        "n": 1,
    }
    assert result.usage.total_tokens == 12


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "provider_unauthorized"),
        (403, "provider_unauthorized"),
        (429, "provider_busy"),
        (503, "provider_unavailable"),
        (400, "provider_rejected"),
        (302, "provider_rejected"),
    ],
)
async def test_http_error_no_retry_or_response_leak(status, code):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            status, text="SECRET upstream body", headers={"location": "http://evil"}
        )

    provider = LlamaCppProvider(Settings(), httpx.MockTransport(handler))
    try:
        with pytest.raises(IntelligenceError) as error:
            await provider.infer(InferenceRequest(**request()), "alias")
        assert error.value.code == code
        assert "SECRET" not in str(error.value)
        assert len(calls) == 1
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "body",
    [
        [],
        {},
        {"choices": []},
        {"choices": [None]},
        {"choices": [{"message": {"role": "assistant", "content": None}, "finish_reason": "stop"}]},
        {
            "choices": [
                {"message": {"role": "assistant", "content": "x"}, "finish_reason": "tool_calls"}
            ]
        },
        response(usage={"prompt_tokens": True, "completion_tokens": 2, "total_tokens": 3}),
        response(usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 1}),
        response(usage={"prompt_tokens": 1, "completion_tokens": 2048, "total_tokens": 2049}),
    ],
)
async def test_malformed_provider(body):
    provider = LlamaCppProvider(
        Settings(), httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(IntelligenceError, match="invalid response"):
            await provider.infer(InferenceRequest(**request()), "alias")
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "kind,code",
    [
        ("timeout", "provider_timeout"),
        ("connection", "provider_unavailable"),
        ("json", "invalid_provider_response"),
        ("compressed", "invalid_provider_response"),
        ("body_size", "response_limit"),
        ("output_size", "response_limit"),
    ],
)
async def test_provider_resource_failures(kind, code):
    calls = []

    def handler(req):
        calls.append(req)
        if kind == "timeout":
            raise httpx.ReadTimeout("SECRET")
        if kind == "connection":
            raise httpx.ConnectError("SECRET")
        if kind == "json":
            return httpx.Response(200, text="not JSON")
        if kind == "compressed":
            return httpx.Response(200, headers={"content-encoding": "br"}, content=b"secret")
        if kind == "body_size":
            return httpx.Response(200, text="x" * 1025)
        return httpx.Response(200, json=response("あ" * 100))

    provider = LlamaCppProvider(
        Settings(max_response_bytes=1024, max_output_bytes=256), httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(IntelligenceError) as error:
            await provider.infer(InferenceRequest(**request()), "alias")
        assert error.value.code == code
        assert len(calls) == 1
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "status,body,available",
    [(200, {"status": "ok"}, True), (200, {"status": "loading model"}, False), (503, {}, False)],
)
async def test_health_independent_process_status(status, body, available):
    provider = LlamaCppProvider(
        Settings(), httpx.MockTransport(lambda _: httpx.Response(status, json=body))
    )
    try:
        result = await IntelligenceService(Settings(), provider).health()
        assert result["healthy"]
        assert result["providers"][0]["available"] is available
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "url",
    [
        "file:///secret",
        "http://user:secret@localhost",
        "http://a/?key=x",
        "http://a/#x",
        "http://a:99999",
        "http://a\\b",
        "http://a\nb",
        "http://%61/",
    ],
)
def test_invalid_operator_url(url):
    with pytest.raises(ValidationError):
        Settings(provider_url=url)


def test_config_env_and_sanitized_failure(monkeypatch):
    monkeypatch.setenv("FLAMORIS_INTELLIGENCE_MODELS", '[{"id":"local","provider_model":"served"}]')
    monkeypatch.setenv("FLAMORIS_INTELLIGENCE_HTTP_PORT", "9999")
    assert Settings.from_env(http_port=8888).http_port == 8888
    assert Settings.from_env().models[0].id == "local"
    monkeypatch.setenv("FLAMORIS_INTELLIGENCE_PROVIDER_URL", "http://user:SECRET@host")
    with pytest.raises(ValueError) as error:
        Settings.from_env()
    assert "SECRET" not in str(error.value)


def test_no_external_listener_or_duplicate_models():
    with pytest.raises(ValidationError):
        Settings(http_host="0.0.0.0")
    with pytest.raises(ValidationError):
        Settings(
            models=(
                ModelEntry(id="same", provider_model="a"),
                ModelEntry(id="same", provider_model="b"),
            )
        )
