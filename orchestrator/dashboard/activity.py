# Copyright 2026 ZyvorAI Labs Private Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
