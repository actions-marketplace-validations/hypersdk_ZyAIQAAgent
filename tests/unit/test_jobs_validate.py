"""Unit tests for dashboard job parameter validation (orchestrator/dashboard/jobs.py)."""

from __future__ import annotations

import pytest

from orchestrator.dashboard.jobs import VALID_KINDS, _redact_params, _validate


def test_password_redacted_but_url_kept():
    red = _redact_params({"url": "https://x.io", "username": "admin", "password": "s3cret"})
    assert red["password"] == "***"
    assert red["username"] == "admin"
    assert red["url"] == "https://x.io"


def test_redact_leaves_empty_password_untouched():
    red = _redact_params({"password": ""})
    assert red["password"] == ""  # nothing to hide


def test_redact_does_not_mutate_original():
    orig = {"password": "s3cret"}
    _redact_params(orig)
    assert orig["password"] == "s3cret"


def test_flow_and_route_sweep_registered():
    assert "flow" in VALID_KINDS
    assert "route_sweep" in VALID_KINDS


def test_flow_requires_url_scheme():
    with pytest.raises(ValueError):
        _validate("flow", {"url": "zyvor.dev", "description": "go to /"})


def test_flow_requires_description():
    with pytest.raises(ValueError):
        _validate("flow", {"url": "https://zyvor.dev", "description": "  "})


def test_flow_clean_defaults():
    clean = _validate("flow", {"url": "https://zyvor.dev", "description": "go to /"})
    assert clean["url"] == "https://zyvor.dev"
    assert clean["record"] is True  # default on
    assert clean["steps_mode"] is False
    assert clean["insecure"] is False


def test_flow_record_toggle_off():
    clean = _validate("flow", {"url": "https://x.io", "description": "go to /", "record": False})
    assert clean["record"] is False


def test_route_sweep_routes_filtered_and_defaulted():
    clean = _validate("route_sweep", {"url": "https://x.io", "routes": "/, /a, bad, /b"})
    assert clean["routes"] == ["/", "/a", "/b"]
    # empty → defaults to root
    clean2 = _validate("route_sweep", {"url": "https://x.io", "routes": "nothing-valid"})
    assert clean2["routes"] == ["/"]


def test_route_sweep_viewports_whitelist():
    clean = _validate("route_sweep", {"url": "https://x.io", "viewports": ["desktop", "mobile", "watch"]})
    assert clean["viewports"] == ["desktop", "mobile"]


def test_route_sweep_auto_and_max_pages():
    clean = _validate("route_sweep", {"url": "https://x.io", "auto": True, "max_pages": 999})
    assert clean["auto"] is True
    assert clean["max_pages"] == 40  # clamped


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        _validate("not_a_real_kind", {})
