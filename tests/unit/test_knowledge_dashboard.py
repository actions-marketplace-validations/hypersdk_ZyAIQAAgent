# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Dashboard knowledge proxy smoke tests (no Qdrant/LLM required)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator.webhook import create_app


def test_knowledge_status_reports_unavailable_without_extras() -> None:
    client = TestClient(create_app())
    response = client.get("/api/dashboard/knowledge/status")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "deps_installed" in payload


def test_knowledge_suggestions_are_non_empty() -> None:
    client = TestClient(create_app())
    response = client.get("/api/dashboard/knowledge/suggestions")
    assert response.status_code == 200
    assert len(response.json()["suggestions"]) >= 1


def test_ask_without_extras_returns_501() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/dashboard/ask",
        json={"question": "How does PacketWolf egress work?"},
    )
    # 501 when extras missing; 503 if extras present but unconfigured.
    assert response.status_code in {501, 503}
    assert "detail" in response.json()
