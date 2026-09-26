"""Bounded MCP protocol ping; never probes or activates the model provider."""

import asyncio
import logging
import sys

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from .config import Settings


async def check(settings: Settings) -> None:
    host = "[::1]" if settings.http_host == "::1" else settings.http_host
    url = f"http://{host}:{settings.http_port}{settings.mcp_path}"
    # One deadline includes negotiation, ping, and client cleanup. No retries.
    async with asyncio.timeout(2):
        async with httpx2.AsyncClient(trust_env=False, follow_redirects=False, timeout=2) as http:
            async with Client(
                streamable_http_client(url, http_client=http), read_timeout_seconds=2
            ) as client:
                await client.send_ping()


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
