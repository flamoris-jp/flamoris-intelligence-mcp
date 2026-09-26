"""Operator-controlled configuration. Callers cannot supply endpoints or paths."""

import json
import os
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator

from .contracts import StrictModel


class ModelEntry(StrictModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    provider_model: str = Field(min_length=1, max_length=512)
    context_tokens: int = Field(default=32768, ge=1024, le=1048576)
    max_output_tokens: int = Field(default=4096, ge=1, le=32768)

    @model_validator(mode="after")
    def budget(self):
        if self.max_output_tokens + 512 >= self.context_tokens:
            raise ValueError("Output budget must leave input and template space")
        return self


class Settings(StrictModel):
    provider_url: str = "http://127.0.0.1:8081"
    provider_api_key: SecretStr | None = Field(default=None, repr=False)
    models: tuple[ModelEntry, ...] = (ModelEntry(id="gpt-oss-20b", provider_model="gpt-oss-20b"),)
    timeout_seconds: float = Field(default=120, gt=0, le=300, allow_inf_nan=False)
    health_timeout_seconds: float = Field(default=5, gt=0, le=30, allow_inf_nan=False)
    max_input_bytes: int = Field(default=65536, ge=1, le=262144)
    max_response_bytes: int = Field(default=1048576, ge=256, le=4194304)
    max_output_bytes: int = Field(default=262144, ge=1, le=1048576)
    max_concurrency: int = Field(default=1, ge=1, le=16)
    transport: Literal["stdio", "streamable-http"] = "stdio"
    http_host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    http_port: int = Field(default=8767, ge=1, le=65535)
    mcp_path: str = "/mcp"

    @field_validator("provider_url")
    @classmethod
    def valid_url(cls, value):
        try:
            url = urlsplit(value)
            port = url.port
            if (
                url.scheme not in ("http", "https")
                or not url.hostname
                or url.username is not None
                or url.password is not None
                or url.query
                or url.fragment
                or (port is not None and not 1 <= port <= 65535)
                or any(c.isspace() or ord(c) < 32 for c in value)
                or "\\" in value
                or "%" in url.netloc
            ):
                raise ValueError
        except ValueError:
            raise ValueError("Invalid provider base URL") from None
        return value.rstrip("/")

    @field_validator("mcp_path")
    @classmethod
    def valid_path(cls, value):
        if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*)?", value):
            raise ValueError("Invalid literal MCP path")
        return value

    @model_validator(mode="after")
    def valid_models(self):
        if not 1 <= len(self.models) <= 16 or len({m.id for m in self.models}) != len(self.models):
            raise ValueError("Configure 1 to 16 unique model IDs")
        if self.max_output_bytes > self.max_response_bytes:
            raise ValueError("Output bytes must not exceed response bytes")
        return self

    @classmethod
    def from_env(cls, **overrides):
        values = {}
        integer_fields = {
            "max_input_bytes", "max_response_bytes", "max_output_bytes", "max_concurrency", "http_port"
        }
        float_fields = {"timeout_seconds", "health_timeout_seconds"}
        try:
            for name in cls.model_fields:
                raw = os.environ.get("FLAMORIS_INTELLIGENCE_" + name.upper())
                if raw is None:
                    continue
                if name in integer_fields:
                    values[name] = int(raw)
                elif name in float_fields:
                    values[name] = float(raw)
                elif name == "models":
                    entries = json.loads(raw)
                    if not isinstance(entries, list):
                        raise ValueError
                    values[name] = tuple(ModelEntry.model_validate(entry) for entry in entries)
                elif name == "provider_api_key":
                    values[name] = SecretStr(raw)
                else:
                    values[name] = raw
            values.update({k: v for k, v in overrides.items() if v is not None})
            return cls(**values)
        except (ValueError, TypeError, ValidationError):
            # Never echo environment values (URLs/credentials can be private).
            raise ValueError("Invalid FLAMORIS_INTELLIGENCE configuration; see README") from None
