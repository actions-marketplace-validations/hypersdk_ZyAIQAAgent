"""Durable recurring-job scheduler.

This replaces the in-memory scheduler while preserving its public API.
"""

from __future__ import annotations

from typing import Any

from orchestrator.dashboard.durable_jobs import get_service
from orchestrator.persistence.store import get_store


def add(kind: str, params: dict[str, Any], interval_s: int) -> dict[str, Any]:
    entry = get_store().add_schedule(kind, params, interval_s, requested_by="legacy-dashboard")
    get_service().start()
    return entry


def remove(sid: str) -> bool:
    return get_store().remove_schedule(sid)


def listing() -> list[dict[str, Any]]:
    return get_store().list_schedules()


def _ensure_thread() -> None:
    get_service().start()
