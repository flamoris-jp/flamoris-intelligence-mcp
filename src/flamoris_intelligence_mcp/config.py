"""MCP transport configuration over the shared provider settings."""

import re
from typing import Literal

from pydantic import Field, field_validator

from flamoris_intelligence.config import ModelEntry
from flamoris_intelligence.config import Settings as ProviderSettings

__all__ = ["ModelEntry", "Settings"]


class Settings(ProviderSettings):
    transport: Literal["stdio", "streamable-http"] = "stdio"
    http_host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    http_port: int = Field(default=8767, ge=1, le=65535)
    mcp_path: str = "/mcp"

    @field_validator("mcp_path")
    @classmethod
    def valid_path(cls, value):
        if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*)?", value):
            raise ValueError("Invalid literal MCP path")
        return value
