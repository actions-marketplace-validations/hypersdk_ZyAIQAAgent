# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised when required MCP server configuration is missing."""


@dataclass(frozen=True)
class MCPConfig:
    base_url: str
    api_token: str
    transport: str
    host: str
    port: int
    default_wait_s: float
    max_wait_s: float
    poll_interval_s: float


def load_config() -> MCPConfig:
    base_url = os.environ.get("ZYVOR_API_BASE_URL", "").strip().rstrip("/")
    api_token = os.environ.get("ZYVOR_API_TOKEN", "").strip()
    if not base_url:
        raise ConfigError("ZYVOR_API_BASE_URL is required")
    if not api_token:
        raise ConfigError("ZYVOR_API_TOKEN is required")

    transport = os.environ.get("ZYVOR_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in ("stdio", "streamable-http"):
        raise ConfigError("ZYVOR_MCP_TRANSPORT must be 'stdio' or 'streamable-http'")

    return MCPConfig(
        base_url=base_url,
        api_token=api_token,
        transport=transport,
        host=os.environ.get("ZYVOR_MCP_HOST", "127.0.0.1").strip(),
        port=int(os.environ.get("ZYVOR_MCP_PORT", "8090")),
        default_wait_s=float(os.environ.get("ZYVOR_MCP_DEFAULT_WAIT_S", "20")),
        max_wait_s=float(os.environ.get("ZYVOR_MCP_MAX_WAIT_S", "90")),
        poll_interval_s=float(os.environ.get("ZYVOR_MCP_POLL_INTERVAL_S", "2")),
    )
