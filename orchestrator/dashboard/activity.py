"""In-memory activity feeds for the dashboard: recent jobs + webhook events."""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

_lock = threading.Lock()
_jobs: deque[dict[str, Any]] = deque(maxlen=15)
_webhooks: deque[dict[str, Any]] = deque(maxlen=8)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_job(kind: str, ok: bool, brief: str, duration_s: float) -> None:
    with _lock:
        _jobs.appendleft(
            {
                "type": "job",
                "kind": kind,
                "ok": ok,
                "brief": brief[:160],
                "duration_s": round(duration_s, 1),
                "at": _now(),
            }
        )


def record_webhook(event: str, repo: str | None, detail: str = "") -> None:
    with _lock:
        _webhooks.appendleft(
            {
                "type": "webhook",
                "event": event,
                "repo": repo,
                "detail": detail[:120],
                "at": _now(),
            }
        )


def recent(limit: int = 15) -> list[dict[str, Any]]:
    with _lock:
        merged = list(_jobs) + list(_webhooks)
    merged.sort(key=lambda item: item["at"], reverse=True)
    return merged[:limit]


def last_webhook() -> dict[str, Any] | None:
    with _lock:
        return _webhooks[0] if _webhooks else None
