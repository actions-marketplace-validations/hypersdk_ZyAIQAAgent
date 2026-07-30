"""Remediation agent gate tests (no LLM required)."""

from __future__ import annotations

import pytest

from knowledge.config import clear_settings_cache
from knowledge.remediation import clear_remediation_agent_cache, plan_remediation


def test_remediation_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_REMEDIATION_AGENT", "false")
    clear_settings_cache()
    clear_remediation_agent_cache()
    result = plan_remediation(issue="restart hubble-relay")
    assert result["enabled"] is False
    assert "ENABLE_REMEDIATION_AGENT" in (result.get("blocked_reason") or "")
    clear_settings_cache()
    clear_remediation_agent_cache()
