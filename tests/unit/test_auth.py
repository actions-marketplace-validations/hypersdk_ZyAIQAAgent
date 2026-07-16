"""Unit tests for dashboard auth: tokens, credentials, and login rate limiting."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def auth(monkeypatch):
    monkeypatch.setenv("DASHBOARD_PASSWORD", "Admin@321")
    monkeypatch.setenv("DASHBOARD_USER", "admin")
    from orchestrator.dashboard import auth as auth_mod

    importlib.reload(auth_mod)
    return auth_mod


def test_enabled_when_password_set(auth):
    assert auth.enabled() is True


def test_verify_credentials(auth):
    assert auth.verify_credentials("admin", "Admin@321") is True
    assert auth.verify_credentials("admin", "wrong") is False
    assert auth.verify_credentials("root", "Admin@321") is False


def test_token_roundtrip(auth):
    token, max_age = auth.issue_token()
    assert max_age > 0
    assert auth.validate_token(token) is True


def test_tampered_token_rejected(auth):
    token, _ = auth.issue_token()
    expiry, _sig = token.split(":", 1)
    assert auth.validate_token(f"{expiry}:deadbeef") is False


def test_expired_token_rejected(auth):
    # forge an expiry in the past with a valid signature
    past = 1
    sig = auth._sign(past)
    assert auth.validate_token(f"{past}:{sig}") is False


def test_rate_limit_trips_and_clears(auth):
    ip = "203.0.113.7"
    for _ in range(auth.RL_MAX_FAILURES):
        assert auth.rate_limited(ip) == 0
        auth.record_failure(ip)
    assert auth.rate_limited(ip) > 0
    # a different IP is unaffected
    assert auth.rate_limited("203.0.113.8") == 0
    # success clears the tripped IP's counters (simulate after lockout window in prod)
    auth.record_success(ip)
    assert ip not in auth._rl_locked_until


def test_requires_auth_paths(auth):
    assert auth.requires_auth("/dashboard") is True
    assert auth.requires_auth("/api/dashboard/jobs") is True
    assert auth.requires_auth("/health") is False
    assert auth.requires_auth("/webhook/github") is False
    assert auth.requires_auth("/api/login") is False
