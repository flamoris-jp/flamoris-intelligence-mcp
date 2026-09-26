"""Manual MCP smoke: assumes an operator has already activated the provider runtime."""

import argparse
import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters


async def smoke(model_id: str):
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
        health = await client.call_tool("system.health")
        print(json.dumps(health.structured_content, indent=2))
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
    asyncio.run(smoke(parser.parse_args().model))
