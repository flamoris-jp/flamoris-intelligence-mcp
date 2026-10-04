import asyncio
import json
import subprocess
import sys

import httpx
import pytest
from pydantic import SecretStr

from flamoris_intelligence import ModelEntry, Settings, create_service
from flamoris_intelligence.contracts import IntelligenceError

MESSAGES = [
    {"role": "system", "content": "caller policy"},
    {"role": "user", "content": "earlier turn"},
    {"role": "assistant", "content": "earlier answer"},
    {"role": "user", "content": "new question"},
]


def direct_request(**kwargs):
    return {"model_id": "public-model", "messages": MESSAGES, **kwargs}


def settings(**kwargs):
    return Settings(
        models=(ModelEntry(id="public-model", provider_model="served-model"),), **kwargs
    )


async def test_direct_messages_use_exact_order_roles_and_model_identity():
    calls = []

    def provider(req):
        calls.append(req)
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "served-model"}]})
        return httpx.Response(
            200,
            json={
                "model": "served-model",
                "choices": [
                    {"message": {"role": "assistant", "content": "answer"}, "finish_reason": "stop"}
                ],
            },
        )

    service = create_service(settings(), transport=httpx.MockTransport(provider))
    try:
        assert (await service.model_available("public-model"))["available"]
        assert "tool" not in service.capability("text.generate")
        result = await service.execute_messages(direct_request())
        assert result["ok"] and result["provider_id"] == "llamacpp"
        assert result["model_id"] == "public-model" and result["text"] == "answer"
        assert json.loads(calls[-1].content)["messages"] == MESSAGES
        assert json.loads(calls[-1].content)["model"] == "served-model"
        assert len(calls) == 2
    finally:
        await service.close()


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "tool", "content": "x"}],
        [{"role": "user", "content": 42}],
        [{"role": "user", "content": "x", "path": "/private"}],
        [{"role": "user", "content": "\ud800"}],
        [{"role": "user", "content": "x" * 65537}],
        [{"role": "user", "content": " "}],
        [{"role": "user", "content": "x"}] * 129,
    ],
)
async def test_invalid_direct_messages_rejected_before_provider(messages):
    calls = []
    service = create_service(
        settings(), transport=httpx.MockTransport(lambda req: calls.append(req))
    )
    try:
        result = await service.execute_messages(direct_request(messages=messages))
        assert result["error"]["code"] == "invalid_request"
        assert calls == []
    finally:
        await service.close()


async def test_direct_exact_model_probe_rejects_wrong_alias_and_bounds_concurrency():
    entered = asyncio.Event()
    release = asyncio.Event()

    async def provider(req):
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"data": [{"id": "other-model"}]})

    service = create_service(settings(), transport=httpx.MockTransport(provider))
    task = asyncio.create_task(service.model_available("public-model"))
    try:
        await entered.wait()
        with pytest.raises(IntelligenceError) as error:
            await service.model_available("public-model")
        assert error.value.code == "busy"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        with pytest.raises(IntelligenceError) as error:
            await service.model_available("public-model")
        assert error.value.code == "provider_unavailable"
        assert not service.health_active
    finally:
        await service.close()


async def test_direct_returned_model_mismatch_normalized():
    service = create_service(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "model": "wrong-model",
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "SECRET"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        ),
    )
    try:
        result = await service.execute_messages(direct_request())
        assert result["error"]["code"] == "invalid_provider_response"
        assert "SECRET" not in json.dumps(result)
    finally:
        await service.close()


async def test_direct_openai_messages_preserved_without_stored_remote_conversation():
    calls = []
    configured = Settings(
        models=(ModelEntry(id="public-model", provider_id="openai", provider_model="gpt-5-mini"),),
        openai_api_key=SecretStr("test-only"),
        openai_input_usd_per_million=1,
        openai_output_usd_per_million=1,
        openai_max_request_usd=1,
    )

    def provider(req):
        calls.append(req)
        return httpx.Response(
            200,
            json={
                "model": "gpt-5-mini",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "answer"}],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
            },
        )

    service = create_service(configured, transport=httpx.MockTransport(provider))
    try:
        result = await service.execute_messages(direct_request())
        assert result["ok"] and result["provider_id"] == "openai"
        payload = json.loads(calls[0].content)
        assert payload["input"] == MESSAGES and "instructions" not in payload
        assert payload["store"] is False and payload["background"] is False
        assert payload["tools"] == [] and payload["stream"] is False
        assert "previous_response_id" not in payload
        assert len(calls) == 1
    finally:
        await service.close()


def test_neutral_boundary_imports_without_mcp_sdk():
    # A consumer installs only base dependencies. Prevent accidental SDK imports,
    # even when the test environment also contains external-facade dependencies.
    script = """
import importlib.abc
import sys
class NoMCP(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mcp" or fullname.startswith("mcp.") or fullname == "httpx2":
            raise AssertionError("Internal execution imported MCP SDK")
sys.meta_path.insert(0, NoMCP())
from flamoris_intelligence import Settings, create_service
service = create_service(Settings())
assert service.model("gpt-oss-20b")["model_id"] == "gpt-oss-20b"
import asyncio
asyncio.run(service.close())
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True)
