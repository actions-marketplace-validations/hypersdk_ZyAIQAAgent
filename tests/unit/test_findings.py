"""Tests for the findings store and auto-collection ('what's broken')."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def findings():
    from orchestrator.dashboard import findings as f

    importlib.reload(f)
    f.clear()
    return f


def test_add_and_listing(findings):
    findings.add("api_contract", "high", "GET /x broke", "boom", "https://x.io", "GET /x")
    L = findings.listing()
    assert L["total"] == 1
    assert L["counts"]["high"] == 1
    assert L["findings"][0]["title"] == "GET /x broke"


def test_invalid_severity_defaults_medium(findings):
    findings.add("vitals", "banana", "slow")
    assert findings.listing()["findings"][0]["severity"] == "medium"


def test_severity_filter(findings):
    findings.add("a", "high", "h")
    findings.add("b", "low", "l")
    assert findings.listing(severity="high")["total"] == 1
    assert findings.listing(severity="low")["findings"][0]["title"] == "l"


def test_clear(findings):
    findings.add("a", "high", "h")
    assert findings.clear() == 1
    assert findings.listing()["total"] == 0


def test_newest_first(findings):
    findings.add("a", "high", "first")
    findings.add("a", "high", "second")
    assert findings.listing()["findings"][0]["title"] == "second"


def test_auto_findings_api_contract(findings, monkeypatch):
    from orchestrator.dashboard import jobs

    monkeypatch.setattr(jobs, "log_progress", lambda *a, **k: None)
    jobs._auto_findings("api_contract", "https://api.x.io", {"endpoints": [
        {"method": "GET", "path": "/u", "status": 200, "ok": False, "schema_errors": ["$.email: required property missing"]},
        {"method": "GET", "path": "/ok", "status": 200, "ok": True, "schema_errors": []},
    ]})
    L = findings.listing()
    assert L["total"] == 1  # only the failing endpoint
    assert "schema violation" in L["findings"][0]["title"]


def test_auto_findings_vitals_grades(findings, monkeypatch):
    from orchestrator.dashboard import jobs

    monkeypatch.setattr(jobs, "log_progress", lambda *a, **k: None)
    jobs._auto_findings("vitals", "https://x.io", {"metrics": {
        "LCP": {"value": 5000, "grade": "poor"},
        "TTFB": {"value": 1080, "grade": "needs-improvement"},
        "CLS": {"value": 0.01, "grade": "good"},
    }})
    counts = findings.listing()["counts"]
    assert counts["high"] == 1 and counts["medium"] == 1  # poor→high, ni→medium, good→none


def test_auto_findings_auth_failures_are_high(findings, monkeypatch):
    from orchestrator.dashboard import jobs

    monkeypatch.setattr(jobs, "log_progress", lambda *a, **k: None)
    jobs._auto_findings("auth_test", "https://x.io", {"checks": [
        {"name": "unauthenticated gated", "ok": False, "detail": "reachable"},
        {"name": "api login", "ok": True, "detail": ""},
    ]})
    L = findings.listing()
    assert L["total"] == 1 and L["findings"][0]["severity"] == "high"
