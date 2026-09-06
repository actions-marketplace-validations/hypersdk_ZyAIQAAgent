# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""MCP server exposing Mission Control's job API to MCP clients (e.g. Hermes Agent).

Talks only to the existing `/api/v2` HTTP API over a Bearer service token — it
does not import `orchestrator.*` and has no access to Playwright/LangGraph
internals. See docs/mcp-server.md for setup and connection recipes.
"""
