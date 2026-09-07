# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""File-backed quarantine list. Same shape as reports/test-index.jsonl —
operator-local, no store-schema change, works on SQLite and Postgres deploys.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()

_DEFAULT_TTL_HOURS = 72
_MAX_REASON = 400


def _iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def test_key(title: str, file: str = "") -> str:
    raw = f"{file.strip()}::{title.strip()}".strip(":")
    slug = re.sub(r"[^a-zA-Z0-9:._/-]+", "-", raw).strip("-").lower()
    return slug[:180] or "unnamed"


def quarantine_path(root: Path | None = None) -> Path:
    from orchestrator.paths import repo_root

    base = root if root is not None else repo_root()
    return Path(base) / "reports" / "quarantine.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"tests": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tests": {}}
    tests = data.get("tests") if isinstance(data, dict) else None
    return {"tests": tests if isinstance(tests, dict) else {}}


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def add(
    title: str,
    *,
    file: str = "",
    reason: str,
    owner: str = "",
    ttl_hours: int = _DEFAULT_TTL_HOURS,
    category: str = "flaky",
    root: Path | None = None,
) -> dict[str, Any]:
    title = (title or "").strip()
    if not title:
        raise ValueError("title is required")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("reason is required")
    ttl_hours = max(1, min(int(ttl_hours), 24 * 30))
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ttl_hours)
    key = test_key(title, file)
    entry = {
        "key": key,
        "title": title[:200],
        "file": (file or "")[:300],
        "reason": reason[:_MAX_REASON],
        "category": (category or "flaky")[:40],
        "owner": (owner or "")[:80],
        "quarantined_at": _iso(now),
        "expires_at": _iso(expires),
        "status": "active",
    }
    path = quarantine_path(root)
    with _lock:
        data = _load(path)
        data["tests"][key] = entry
        _save(path, data)
    return entry


def release(key: str, *, root: Path | None = None) -> bool:
    path = quarantine_path(root)
    with _lock:
        data = _load(path)
        entry = data["tests"].get(key)
        if not entry:
            return False
        entry["status"] = "released"
        entry["released_at"] = _iso()
        _save(path, data)
    return True


def prune_expired(*, root: Path | None = None, now: datetime | None = None) -> int:
    path = quarantine_path(root)
    moment = now or datetime.now(timezone.utc)
    pruned = 0
    with _lock:
        data = _load(path)
        for entry in data["tests"].values():
            if entry.get("status") != "active":
                continue
            expires = _parse_iso(entry.get("expires_at"))
            if expires is not None and expires <= moment:
                entry["status"] = "expired"
                pruned += 1
        if pruned:
            _save(path, data)
    return pruned


def listing(*, root: Path | None = None, include_inactive: bool = False) -> list[dict[str, Any]]:
    prune_expired(root=root)
    path = quarantine_path(root)
    with _lock:
        data = _load(path)
    rows = list(data["tests"].values())
    if not include_inactive:
        rows = [r for r in rows if r.get("status") == "active"]
    rows.sort(key=lambda r: r.get("expires_at") or "", reverse=True)
    return rows


def is_quarantined(title: str, file: str = "", *, root: Path | None = None) -> dict[str, Any] | None:
    prune_expired(root=root)
    key = test_key(title, file)
    path = quarantine_path(root)
    with _lock:
        entry = _load(path)["tests"].get(key)
    if entry and entry.get("status") == "active":
        return entry
    return None
