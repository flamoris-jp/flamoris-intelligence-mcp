import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from flamoris_intelligence_mcp.config import ModelEntry, Settings
from flamoris_intelligence_mcp.contracts import InferenceRequest, IntelligenceError, ProviderResult
from flamoris_intelligence_mcp.openai_provider import OpenAIProvider
from flamoris_intelligence_mcp.service import IntelligenceService


def configured(**kwargs):
    return Settings(
        models=(
            ModelEntry(id="api-small", provider_id="openai", provider_model="configured-snapshot"),
        ),
        openai_api_key=SecretStr("fixture-key"),
        openai_input_usd_per_million=1.0,
        openai_output_usd_per_million=2.0,
        openai_max_request_usd=0.05,
        **kwargs,
    )


def response(**kwargs):
    return {
        "model": "configured-snapshot",
        "status": "completed",
        "error": None,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "hello"}],
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        **kwargs,
    }


async def test_exact_stateless_responses_wire_and_usage():
    calls = []

    def handle(req):
        calls.append(req)
        assert str(req.url) == "https://api.openai.com/v1/responses"
        assert req.headers["authorization"] == "Bearer fixture-key"
        body = json.loads(req.content)
        assert body == {
            "model": "configured-snapshot",
            "input": "question",
            "instructions": "policy",
            "max_output_tokens": 1024,
            "store": False,
            "stream": False,
            "background": False,
            "tools": [],
            "truncation": "disabled",
        }
        return httpx.Response(200, json=response())

    provider = OpenAIProvider(configured(), httpx.MockTransport(handle))
    try:
        result = await provider.infer(
            InferenceRequest(model_id="api-small", input="question", instruction="policy"),
            "configured-snapshot",
        )
        assert result.text == "hello" and result.usage.total_tokens == 12
        assert len(calls) == 1
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "provider_unauthorized"),
        (429, "provider_busy"),
        (500, "provider_unavailable"),
        (302, "provider_rejected"),
    ],
)
async def test_no_retry_no_private_error_body(status, code):
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(
            status,
            json={"secret": "private-key/private-prompt"},
            headers={"Location": "https://elsewhere.invalid"},
        )

    provider = OpenAIProvider(configured(), httpx.MockTransport(handle))
    try:
        with pytest.raises(IntelligenceError) as error:
            await provider.infer(
                InferenceRequest(model_id="api-small", input="hello"), "configured-snapshot"
            )
        assert error.value.code == code and "private" not in str(error.value) and len(calls) == 1
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "body",
    [
        response(output=[{"type": "function_call"}]),
        response(usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 99}),
        response(status="failed"),
        response(
            output=[
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "refusal", "refusal": "no"}],
                }
            ]
        ),
    ],
)
async def test_malformed_or_tools_do_not_become_answers(body):
    provider = OpenAIProvider(
        configured(), httpx.MockTransport(lambda req: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(IntelligenceError):
            await provider.infer(
                InferenceRequest(model_id="api-small", input="hi"), "configured-snapshot"
            )
    finally:
        await provider.close()


async def test_cost_ceiling_rejects_before_dispatch():
    settings = configured().model_copy(update={"openai_max_request_usd": 0.000001})
    calls = []
    provider = OpenAIProvider(settings, httpx.MockTransport(lambda req: calls.append(req)))
    try:
        with pytest.raises(IntelligenceError, match="allowance"):
            await provider.infer(
                InferenceRequest(model_id="api-small", input="hi"), "configured-snapshot"
            )
        assert not calls
    finally:
        await provider.close()


async def test_local_offline_or_busy_does_not_block_api_provider():
    entered = asyncio.Event()

    class Local:
        async def health(self):
            raise IntelligenceError("provider_unavailable")

        async def infer(self, req, model):
            entered.set()
            await asyncio.Event().wait()

    class Remote:
        async def health(self):
            pass

        async def infer(self, req, model):
            return ProviderResult(text="remote", finish_reason="stop")

    settings = configured().model_copy(
        update={"models": (ModelEntry(id="local", provider_model="local"), *configured().models)}
    )
    service = IntelligenceService(settings, {"llamacpp": Local(), "openai": Remote()})
    health = await service.health()
    assert [p["available"] for p in health["providers"]] == [False, True]
    task = asyncio.create_task(service.execute({"model_id": "local", "input": "hi"}))
    await entered.wait()
    try:
        result = await service.execute({"model_id": "api-small", "input": "hi"})
        assert result["ok"] and result["provider_id"] == "openai" and result["text"] == "remote"
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert service.active == 0


async def test_cancel_leaves_no_retry_and_releases_http_work():
    entered = asyncio.Event()
    exited = asyncio.Event()
    calls = []

    async def handle(req):
        calls.append(req)
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            exited.set()

    provider = OpenAIProvider(configured(), httpx.MockTransport(handle))
    task = asyncio.create_task(
        provider.infer(InferenceRequest(model_id="api-small", input="hi"), "configured-snapshot")
    )
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert exited.is_set() and len(calls) == 1
    await provider.close()
