"""Manual MCP smoke: assumes an operator has already activated the provider runtime."""

import argparse
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager

import httpx2
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client


@asynccontextmanager
async def connect(url: str | None):
    if url:
        async with httpx2.AsyncClient(trust_env=False, follow_redirects=False, timeout=310) as http:
            async with Client(
                streamable_http_client(url, http_client=http), read_timeout_seconds=310
            ) as client:
                yield client
        return
    env = {
        key: value for key, value in os.environ.items() if key.startswith("FLAMORIS_INTELLIGENCE_")
    }
    env["FLAMORIS_INTELLIGENCE_TRANSPORT"] = "stdio"
    async with Client(
        StdioServerParameters(
            command=sys.executable, args=["-m", "flamoris_intelligence_mcp"], env=env
        ),
        read_timeout_seconds=310,
    ) as client:
        yield client


async def smoke(model_id: str, url: str | None = None, discovery_only: bool = False):
    async with connect(url) as client:
        health = await client.call_tool("system.health")
        print(json.dumps(health.structured_content, indent=2))
        if health.is_error or not health.structured_content.get("healthy"):
            raise SystemExit("MCP health failed")
        for tool, key, id_key in (
            ("models.list", "models", "model_id"),
            ("capabilities.list", "capabilities", "capability_id"),
        ):
            result = await client.call_tool(tool)
            if result.is_error or not result.structured_content.get(key):
                raise SystemExit("MCP discovery failed")
            print(json.dumps({key: [item[id_key] for item in result.structured_content[key]]}))
        if discovery_only:
            return
        if health.is_error or not health.structured_content["providers"][0]["available"]:
            raise SystemExit(
                "Provider is not ready; activate it through its runtime manager first."
            )
        result = await client.call_tool(
            "inference.execute",
            {
                "request": {
                    "model_id": model_id,
                    "input": "Reply with a short greeting.",
                    "max_output_tokens": 256,
                    "temperature": 0.0,
                }
            },
        )
        print(json.dumps(result.structured_content, indent=2, ensure_ascii=False))
        if result.is_error:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-oss-20b")
    parser.add_argument("--url", help="Connect to an existing MCP HTTP endpoint")
    parser.add_argument("--discovery-only", action="store_true", help="Skip inference")
    args = parser.parse_args()
    asyncio.run(smoke(args.model, args.url, args.discovery_only))
