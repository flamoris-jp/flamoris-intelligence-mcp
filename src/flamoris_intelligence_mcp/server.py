"""Official MCP SDK owns protocol/transport; handlers share one bounded service."""

import argparse
import json
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from . import __version__
from .config import Settings
from .contracts import CAPABILITIES, IntelligenceError
from .llamacpp import LlamaCppProvider
from .service import IntelligenceService


def tool_result(data: dict) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(data, ensure_ascii=True))],
        structuredContent=data,
        isError=data.get("ok") is False,
    )


def create_server(
    settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None
) -> MCPServer:
    settings = settings or Settings.from_env()
    provider = LlamaCppProvider(settings, transport)
    service = IntelligenceService(settings, provider)

    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield None
        finally:
            await provider.close()

    server = MCPServer(
        "FLAMORIS Intelligence", version=__version__, lifespan=lifespan, log_level="WARNING"
    )
    read_only = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )

    @server.tool(name="system.health", annotations=read_only)
    async def health() -> CallToolResult:
        """Report process health separately from bounded provider reachability."""
        try:
            return tool_result(await service.health())
        except Exception:
            return tool_result({"ok": False, "error": IntelligenceError("internal_error").public()})

    @server.tool(name="capabilities.list", annotations=read_only)
    async def capabilities() -> CallToolResult:
        """List configured operations; discovery does not activate or probe a runtime."""
        return tool_result({"capabilities": [service.capability(c) for c in CAPABILITIES]})

    @server.tool(name="capabilities.get", annotations=read_only)
    async def capability(capability_id: str) -> CallToolResult:
        """Get one operation by its capability ID."""
        try:
            return tool_result(service.capability(capability_id))
        except IntelligenceError as exc:
            return tool_result({"ok": False, "error": exc.public()})

    @server.tool(name="models.list", annotations=read_only)
    async def models() -> CallToolResult:
        """List operator-configured model aliases; this is not live model discovery."""
        return tool_result({"models": [service.model(m) for m in service.models]})

    @server.tool(name="models.get", annotations=read_only)
    async def model(model_id: str) -> CallToolResult:
        """Get one configured model and its limits without exposing provider paths."""
        try:
            return tool_result(service.model(model_id))
        except IntelligenceError as exc:
            return tool_result({"ok": False, "error": exc.public()})

    @server.tool(
        name="inference.execute",
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
        ),
    )
    async def execute(request: dict[str, Any]) -> CallToolResult:
        """Execute once with no persistence/retry. request: model_id, input, optional instruction,
        capability_id (text.generate/reasoning.generate/code.generate), max_output_tokens (1024),
        temperature (0.7), timeout_seconds. Inputs and outputs go to the configured provider only.
        Cancellation closes local work; remote GPU completion is not guaranteed.
        """
        return tool_result(await service.execute(request))

    return server


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="FLAMORIS Intelligence MCP")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"))
    parser.add_argument("--host", dest="http_host", choices=("127.0.0.1", "::1"))
    parser.add_argument("--port", dest="http_port", type=int)
    parser.add_argument("--mcp-path")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env(**vars(args))
    except ValueError as exc:
        parser.error(str(exc))
    server = create_server(settings)
    if settings.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(
            transport="streamable-http",
            host=settings.http_host,
            port=settings.http_port,
            streamable_http_path=settings.mcp_path,
            stateless_http=True,
            json_response=True,
            max_request_body_size=2 * 1024 * 1024,
        )


if __name__ == "__main__":
    main()
