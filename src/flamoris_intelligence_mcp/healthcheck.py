"""Bounded MCP discovery check; never probes or activates the model provider."""

import asyncio
import logging
import sys

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from .config import Settings


async def reject_redirect(response: httpx2.Response) -> None:
    # SDK discovery may otherwise follow same-origin redirects itself.
    if 300 <= response.status_code < 400:
        raise ValueError("Healthcheck redirects are not allowed")


async def check(settings: Settings) -> None:
    host = "[::1]" if settings.http_host == "::1" else settings.http_host
    url = f"http://{host}:{settings.http_port}{settings.mcp_path}"
    # One deadline includes negotiation, discovery, and client cleanup.
    async with asyncio.timeout(2):
        async with httpx2.AsyncClient(
            trust_env=False,
            follow_redirects=False,
            timeout=2,
            event_hooks={"response": [reject_redirect]},
        ) as http:
            async with Client(
                streamable_http_client(url, http_client=http), read_timeout_seconds=2
            ) as client:
                tools = await client.list_tools()
                if not {"system.health", "models.list", "inference.execute"}.issubset(
                    {tool.name for tool in tools.tools}
                ):
                    raise ValueError("Intelligence MCP tools missing")


def main() -> int:
    # Health output is stored in Docker inspect. Never copy SDK exception details,
    # environment configuration, endpoints, or credentials into that output.
    logging.disable(logging.CRITICAL)
    try:
        asyncio.run(check(Settings.from_env()))
    except Exception:
        print("MCP healthcheck failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
