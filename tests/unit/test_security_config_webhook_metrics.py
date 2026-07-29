import hashlib
import hmac

import pytest

from orchestrator.observability.metrics import inc, render, set_gauge
from orchestrator.persistence.store import MissionControlStore
from orchestrator.security.config import SecurityConfigurationError, validate_runtime_security
from orchestrator.security.webhook import WebhookSecurityError, verify_github_webhook


def test_production_config_is_fail_closed(monkeypatch):
    monkeypatch.setenv("ZYVOR_ENV", "production")
    for key in ("DASHBOARD_PASSWORD", "DASHBOARD_SECRET", "GITHUB_WEBHOOK_SECRET", "ZYVOR_TARGET_ALLOWLIST"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SecurityConfigurationError):
        validate_runtime_security()


def test_production_config_accepts_secure_minimum(monkeypatch):
    monkeypatch.setenv("ZYVOR_ENV", "production")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "p" * 16)
    monkeypatch.setenv("DASHBOARD_SECRET", "s" * 32)
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "w" * 32)
    monkeypatch.setenv("ZYVOR_TARGET_ALLOWLIST", "zyvor.dev,*.zyvor.dev")
    monkeypatch.setenv("ZYVOR_AGENT_MODE", "read_only")
    validate_runtime_security()


def test_webhook_signature_and_replay(tmp_path):
    store = MissionControlStore(tmp_path / "state.db")
    payload = b'{"hello":"world"}'
    secret = "webhook-secret"
    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    first = verify_github_webhook(
        payload, signature, secret, event="push", delivery_id="delivery-1", store=store
    )
    second = verify_github_webhook(
        payload, signature, secret, event="push", delivery_id="delivery-1", store=store
    )
    assert first.accepted and not first.duplicate
    assert second.duplicate and not second.accepted


def test_webhook_rejects_missing_secret(monkeypatch, tmp_path):
    monkeypatch.delenv("ZYVOR_ALLOW_UNSIGNED_WEBHOOKS", raising=False)
    with pytest.raises(WebhookSecurityError):
        verify_github_webhook(
            b"{}", None, "", event="push", delivery_id="d", store=MissionControlStore(tmp_path / "s.db")
        )


def test_prometheus_metrics_render():
    inc("zyvor_qa_test_counter_total", kind="smoke")
    set_gauge("zyvor_qa_test_gauge", 2, worker="one")
    text = render()
    assert 'zyvor_qa_test_counter_total{kind="smoke"}' in text
    assert 'zyvor_qa_test_gauge{worker="one"} 2' in text
