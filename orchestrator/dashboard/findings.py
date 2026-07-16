"""Findings store — the developer-facing "what's broken" list.

Every job automatically records the issues it discovers (broken endpoints,
schema violations, failed auth/live-data checks, poor Web Vitals, audit
failures) here. The dashboard renders them grouped by severity, and they are
exportable so developers / testers / agents get an actionable bug list.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

# severity → rank (higher = worse), for sorting/grouping
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

_lock = threading.Lock()
_findings: deque[dict[str, Any]] = deque(maxlen=500)
_seq = 0


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add(source: str, severity: str, title: str, detail: str = "", url: str = "", where: str = "") -> None:
    """Record one finding. `source` = job kind, `where` = endpoint/step/metric."""
    global _seq
    sev = severity if severity in SEVERITY_RANK else "medium"
    with _lock:
        _seq += 1
        _findings.appendleft({
            "id": _seq,
            "source": source,
            "severity": sev,
            "title": title[:200],
            "detail": (detail or "")[:600],
            "where": (where or "")[:200],
            "url": (url or "")[:300],
            "at": _iso(),
        })


def record_batch(source: str, url: str, items: list[dict[str, Any]]) -> int:
    """Bulk-add findings; returns the count added. Each item: {severity,title,detail,where}."""
    for it in items:
        add(source, it.get("severity", "medium"), it.get("title", ""),
            it.get("detail", ""), url, it.get("where", ""))
    return len(items)


def listing(limit: int = 200, severity: str | None = None) -> dict[str, Any]:
    with _lock:
        rows = list(_findings)
    if severity and severity in SEVERITY_RANK:
        rows = [r for r in rows if r["severity"] == severity]
    counts: dict[str, int] = {k: 0 for k in SEVERITY_RANK}
    for r in rows:
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1
    return {"findings": rows[:limit], "total": len(rows), "counts": counts}


def clear() -> int:
    with _lock:
        n = len(_findings)
        _findings.clear()
    return n
