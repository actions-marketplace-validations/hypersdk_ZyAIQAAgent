"""Tests for remediation executor allowlists (no cluster mutation)."""

from __future__ import annotations

import pytest

from knowledge.config import clear_settings_cache
from knowledge.remediation import (
    _restart_allowed,
    clear_remediation_agent_cache,
    plan_remediation,
    resume_remediation,
)


def test_restart_denied_when_executor_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_REMEDIATION_EXECUTOR", "false")
    monkeypatch.setenv("REMEDIATION_RESTART_NAMESPACES", "demo")
    clear_settings_cache()
    ok, reason = _restart_allowed("web-0", "demo")
    assert ok is False
    assert "disabled" in reason.lower()
    clear_settings_cache()


def test_restart_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_REMEDIATION_EXECUTOR", "true")
    monkeypatch.setenv("REMEDIATION_RESTART_NAMESPACES", "demo")
    monkeypatch.setenv("REMEDIATION_RESTART_NAME_PREFIXES", "web-,hubble-")
    clear_settings_cache()
    ok, _ = _restart_allowed("web-0", "demo")
    assert ok is True
    ok, reason = _restart_allowed("db-0", "demo")
    assert ok is False
    assert "PREFIXES" in reason
    ok, reason = _restart_allowed("web-0", "prod")
    assert ok is False
    clear_settings_cache()


def test_resume_requires_enabled_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_REMEDIATION_AGENT", "false")
    clear_settings_cache()
    clear_remediation_agent_cache()
    result = resume_remediation(thread_id="remediation:test", decision="approve")
    assert result["enabled"] is False
    assert plan_remediation(issue="x")["enabled"] is False
    clear_settings_cache()
    clear_remediation_agent_cache()
