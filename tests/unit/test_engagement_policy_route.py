# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""HTTP-level tests for GET /api/v2/engagement-policy."""

from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator.dashboard.jobs import ELEVATED_RISK_KINDS
from orchestrator.webhook import create_app


def test_engagement_policy_defaults_to_required():
    client = TestClient(create_app())
    resp = client.get("/api/v2/engagement-policy")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enforcement"] == "required"
    assert body["elevated_risk_kinds"] == ELEVATED_RISK_KINDS


def test_engagement_policy_reflects_disabled_enforcement(monkeypatch):
    monkeypatch.setenv("ZYVOR_ENGAGEMENT_ENFORCEMENT", "disabled")
    client = TestClient(create_app())
    resp = client.get("/api/v2/engagement-policy")
    assert resp.status_code == 200
    assert resp.json()["enforcement"] == "disabled"
