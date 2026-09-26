import asyncio
import json
import os
import socket
import sys
from contextlib import asynccontextmanager

import httpx
import httpx2
import pytest
import uvicorn
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from flamoris_intelligence_mcp.config import Settings
from flamoris_intelligence_mcp.server import create_server

TOOLS = {
    "system.health",
    "models.list",
    "models.get",
    "capabilities.list",
    "capabilities.get",
    "inference.execute",
}


def fake_response():
    return {
        "choices": [
            {"message": {"role": "assistant", "content": "MCP works"}, "finish_reason": "stop"}
        ]
    }


def handler(req):
    if req.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(200, json=fake_response())


@asynccontextmanager
async def serve(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 5)
        sock.close()


@asynccontextmanager
async def http_client(url, mode="auto"):
    async with httpx2.AsyncClient(trust_env=False, timeout=10) as transport:
        async with Client(streamable_http_client(url, http_client=transport), mode=mode) as client:
            yield client


async def assert_contract(client):
    tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == TOOLS
    execute = next(tool for tool in tools if tool.name == "inference.execute")
    schema = execute.input_schema["properties"]["request"]
    assert set(schema["required"]) == {"model_id", "input"}
    assert schema["additionalProperties"] is False
    assert not execute.annotations.idempotent_hint
    health = await client.call_tool("system.health")
    assert health.structured_content["healthy"]
    assert health.structured_content["providers"][0]["available"]
    models = await client.call_tool("models.list")
    assert models.structured_content["models"][0]["model_id"] == "gpt-oss-20b"
    caps = await client.call_tool("capabilities.list")
    assert len(caps.structured_content["capabilities"]) == 3
    result = await client.call_tool(
        "inference.execute", {"request": {"model_id": "gpt-oss-20b", "input": "private prompt"}}
    )
    assert not result.is_error
    assert result.structured_content["text"] == "MCP works"
    assert json.loads(result.content[0].text) == result.structured_content
    rejected = await client.call_tool(
        "inference.execute",
        {
            "request": {
                "model_id": "gpt-oss-20b",
                "input": "private prompt",
                "temperature": "SECRET",
            }
        },
    )
    assert rejected.is_error
    assert rejected.structured_content["error"]["code"] == "invalid_request"
    assert "SECRET" not in str(rejected)
    missing = await client.call_tool("models.get", {"model_id": "missing"})
    assert missing.is_error
    assert missing.structured_content["error"]["code"] == "unknown_model"


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_in_memory_protocol(mode):
    server = create_server(transport=httpx.MockTransport(handler))
    async with Client(server, mode=mode) as client:
        await assert_contract(client)


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_real_http_contract_and_security(mode):
    server = create_server(transport=httpx.MockTransport(handler))
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, max_request_body_size=4096
    )
    async with serve(app) as url:
        async with http_client(url + "/mcp", mode=mode) as client:
            await assert_contract(client)
        # A new client must share the still-open provider after the first disconnects.
        async with http_client(url + "/mcp", mode=mode) as client:
            assert (await client.call_tool("system.health")).structured_content["providers"][0][
                "available"
            ]
        async with httpx.AsyncClient(trust_env=False) as client:
            result = await client.post(url + "/mcp", content=b"x" * 4097)
            assert result.status_code == 413
            result = await client.post(url + "/mcp", json={}, headers={"host": "evil.example"})
            assert result.status_code == 421
            result = await client.post(
                url + "/mcp", json={}, headers={"origin": "https://evil.example"}
            )
            assert result.status_code == 403


async def test_real_stdio_cli(tmp_path):
    async def health(_):
        return JSONResponse({"status": "ok"})

    async def infer(_):
        return JSONResponse(fake_response())

    provider = Starlette(
        routes=[Route("/health", health), Route("/v1/chat/completions", infer, methods=["POST"])]
    )
    async with serve(provider) as url:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "flamoris_intelligence_mcp"],
            cwd=str(tmp_path),
            env={"PATH": os.environ.get("PATH", ""), "FLAMORIS_INTELLIGENCE_PROVIDER_URL": url},
        )
        async with Client(params) as client:
            await assert_contract(client)
    assert list(tmp_path.iterdir()) == []


async def test_two_http_clients_share_capacity():
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow(req):
        if req.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        entered.set()
        await release.wait()
        return httpx.Response(200, json=fake_response())

    server = create_server(Settings(), transport=httpx.MockTransport(slow))
    async with serve(server.streamable_http_app(stateless_http=True, json_response=True)) as url:
        async with http_client(url + "/mcp") as a, http_client(url + "/mcp") as b:
            args = {"request": {"model_id": "gpt-oss-20b", "input": "test"}}
            running = asyncio.create_task(a.call_tool("inference.execute", args))
            await asyncio.wait_for(entered.wait(), 3)
            try:
                result = await b.call_tool("inference.execute", args)
                assert result.is_error
                assert result.structured_content["error"]["code"] == "busy"
            finally:
                release.set()
            assert not (await running).is_error
