"""Fail-closed GitHub webhook verification and replay protection."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from orchestrator.persistence.store import MissionControlStore, get_store


class WebhookSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class WebhookVerification:
    accepted: bool
    duplicate: bool
    payload_sha256: str


def verify_github_webhook(
    payload: bytes,
    signature: str | None,
    secret: str,
    *,
    event: str,
    delivery_id: str,
    store: MissionControlStore | None = None,
) -> WebhookVerification:
    allow_unsigned = os.environ.get("ZYVOR_ALLOW_UNSIGNED_WEBHOOKS", "false").lower() in {
        "1", "true", "yes", "on"
    }
    if not secret:
        if not allow_unsigned:
            raise WebhookSecurityError("GITHUB_WEBHOOK_SECRET is required")
    else:
        if not signature or not signature.startswith("sha256="):
            raise WebhookSecurityError("missing or invalid X-Hub-Signature-256")
        expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise WebhookSecurityError("invalid GitHub webhook signature")

    digest = hashlib.sha256(payload).hexdigest()
    if not delivery_id:
        raise WebhookSecurityError("X-GitHub-Delivery is required")
    fresh = (store or get_store()).record_webhook_delivery(delivery_id, event, digest)
    return WebhookVerification(accepted=fresh, duplicate=not fresh, payload_sha256=digest)
