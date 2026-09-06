# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""End-to-end check that the rate-limit middleware actually applies to
/api/dashboard/* and /api/v2/* through the real FastAPI app, and leaves
unrelated paths (like /health) alone."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestrator.security import rate_limit
from orchestrator.webhook import create_app


@pytest.fixture(autouse=True)
def _clean_rate_limit_state():
    rate_limit.reset()
    yield
    rate_limit.reset()


def test_api_v2_route_gets_429_after_limit(monkeypatch):
    monkeypatch.setenv("ZYVOR_API_RATE_LIMIT", "2")
    monkeypatch.setenv("ZYVOR_API_RATE_WINDOW_S", "60")
    client = TestClient(create_app())

    first = client.get("/api/v2/jobs")
    second = client.get("/api/v2/jobs")
    third = client.get("/api/v2/jobs")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert "Retry-After" in third.headers


def test_health_is_never_rate_limited(monkeypatch):
    monkeypatch.setenv("ZYVOR_API_RATE_LIMIT", "1")
    monkeypatch.setenv("ZYVOR_API_RATE_WINDOW_S", "60")
    client = TestClient(create_app())

    for _ in range(5):
        assert client.get("/health").status_code == 200
