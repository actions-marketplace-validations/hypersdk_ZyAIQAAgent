"""Durable, deduplicated findings store preserving the existing dashboard API."""

from __future__ import annotations

import hashlib
from typing import Any

from orchestrator.persistence.store import get_store

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _fingerprint(source: str, title: str, url: str, where: str) -> str:
    raw = "\x1f".join((source, title.strip().lower(), url.strip().lower(), where.strip().lower()))
    return hashlib.sha256(raw.encode()).hexdigest()


def add(source: str, severity: str, title: str, detail: str = "", url: str = "", where: str = "") -> None:
    sev = severity if severity in SEVERITY_RANK else "medium"
    get_store().add_finding(
        source, sev, title, detail, url, where,
        fingerprint=_fingerprint(source, title, url, where),
    )


def record_batch(source: str, url: str, items: list[dict[str, Any]]) -> int:
    for item in items:
        add(
            source,
            item.get("severity", "medium"),
            item.get("title", ""),
            item.get("detail", ""),
            url,
            item.get("where", ""),
        )
    return len(items)


def listing(limit: int = 200, severity: str | None = None) -> dict[str, Any]:
    return get_store().list_findings(limit, severity)


def clear() -> int:
    return get_store().clear_findings()
