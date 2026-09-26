import asyncio
import os
import socket
import sys
import time

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import RedirectResponse
from starlette.routing import Route
from test_transports import http_client, serve

from flamoris_intelligence_mcp.config import Settings
from flamoris_intelligence_mcp.healthcheck import check, main
from flamoris_intelligence_mcp.server import create_server


@pytest.mark.parametrize("available", [True, False])
async def test_discovery_check_does_not_contact_provider(available):
    calls = []

    def provider(req):
        calls.append(req.url.path)
        return httpx.Response(200 if available else 503, json={"status": "ok"})

    server = create_server(transport=httpx.MockTransport(provider))
    async with serve(server.streamable_http_app(stateless_http=True, json_response=True)) as url:
        settings = Settings(http_port=int(url.rsplit(":", 1)[1]))
        await check(settings)
        assert calls == []
        async with http_client(url + "/mcp") as client:
            health = (await client.call_tool("system.health")).structured_content
            assert health["healthy"] is True
            assert health["providers"][0]["available"] is available
        assert calls == ["/health"]


async def run_module(*args, env, cwd):
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        *args,
        env=env,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), 10)
        return proc.returncode, stdout, stderr
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


async def test_installed_cli_http_environment_and_healthcheck(tmp_path):
    # This is the image CMD using installed package modules, outside the source tree.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FLAMORIS_INTELLIGENCE_")}
    env.update(
        {
            "FLAMORIS_INTELLIGENCE_HTTP_PORT": str(port),
            "FLAMORIS_INTELLIGENCE_MCP_PATH": "/custom/intelligence",
            "FLAMORIS_INTELLIGENCE_PROVIDER_URL": "http://127.0.0.1:1",
            "FLAMORIS_INTELLIGENCE_MODELS": '[{"id":"test-model","provider_model":"alias"}]',
            "FLAMORIS_INTELLIGENCE_MAX_CONCURRENCY": "2",
            "HTTP_PROXY": "http://127.0.0.1:1",
            "HTTPS_PROXY": "http://127.0.0.1:1",
            "ALL_PROXY": "http://127.0.0.1:1",
            "NO_PROXY": "",
        }
    )
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "flamoris_intelligence_mcp",
        "--transport",
        "streamable-http",
        env=env,
        cwd=tmp_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(10):
            while True:
                assert proc.returncode is None
                try:
                    reader, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(0.05)
        code, stdout, stderr = await run_module(
            "-m", "flamoris_intelligence_mcp.healthcheck", env=env, cwd=tmp_path
        )
        assert (code, stdout, stderr) == (0, b"", b"")
        async with http_client(f"http://127.0.0.1:{port}/custom/intelligence") as client:
            models = (await client.call_tool("models.list")).structured_content["models"]
            assert [m["model_id"] for m in models] == ["test-model"]
            health = (await client.call_tool("system.health")).structured_content
            assert health["healthy"] and not health["providers"][0]["available"]
    finally:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), 5)


@pytest.mark.parametrize(
    "key,value",
    [
        ("HTTP_HOST", "0.0.0.0"),
        ("HTTP_HOST", "::"),
        ("HTTP_PORT", "0"),
        ("MCP_PATH", "/bad?secret"),
        ("MAX_CONCURRENCY", "0"),
    ],
)
async def test_invalid_deployment_fails_closed(key, value, tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("FLAMORIS_INTELLIGENCE_")}
    env["FLAMORIS_INTELLIGENCE_" + key] = value
    code, _, stderr = await run_module(
        "-m",
        "flamoris_intelligence_mcp",
        "--transport",
        "streamable-http",
        env=env,
        cwd=tmp_path,
    )
    assert code != 0
    assert b"Invalid FLAMORIS_INTELLIGENCE configuration" in stderr
    assert b"secret" not in stderr
    code, _, stderr = await run_module(
        "-m", "flamoris_intelligence_mcp.healthcheck", env=env, cwd=tmp_path
    )
    assert code == 1
    assert stderr == b"MCP healthcheck failed\n"


async def test_healthcheck_closed_listener():
    # Bound but not listening, so another process cannot take this port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        with pytest.raises(ExceptionGroup):
            await check(Settings(http_port=sock.getsockname()[1]))


async def test_healthcheck_deadline():
    release = asyncio.Event()

    async def hang(reader, writer):
        try:
            await release.wait()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(hang, "127.0.0.1", 0)
    async with server:
        try:
            started = time.monotonic()
            with pytest.raises((TimeoutError, ExceptionGroup)):
                await check(Settings(http_port=server.sockets[0].getsockname()[1]))
            assert time.monotonic() - started < 3
        finally:
            release.set()


async def test_healthcheck_does_not_follow_redirect():
    calls = []

    async def redirect(request):
        calls.append(request.url.path)
        return RedirectResponse("/target", status_code=307)

    app = Starlette(routes=[Route("/{path:path}", redirect, methods=["GET", "POST"])])
    async with serve(app) as url:
        with pytest.raises(ExceptionGroup):
            await check(Settings(http_port=int(url.rsplit(":", 1)[1])))
    assert "/target" not in calls


def test_healthcheck_error_output_is_redacted(monkeypatch, capsys):
    async def fail(_):
        raise ValueError("PRIVATE endpoint credential provider response")

    monkeypatch.setattr("flamoris_intelligence_mcp.healthcheck.check", fail)
    # main runs in a dedicated process in production; undo its logging change here.
    import logging

    previous = logging.root.manager.disable
    try:
        assert main() == 1
    finally:
        logging.disable(previous)
    assert capsys.readouterr().err == "MCP healthcheck failed\n"
