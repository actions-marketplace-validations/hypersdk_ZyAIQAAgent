# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Deterministic failure taxonomy. No LLM — the categories are a rubric
over status history + the error string, the same posture as
agents/chaos/verdict.py.
"""

from __future__ import annotations

from typing import Any

CATEGORIES = (
    "healthy",
    "failing",
    "flaky",
    "selector",
    "assertion",
    "infra",
    "data",
    "unknown",
)

_SELECTOR_MARKERS = (
    "locator",
    "strict mode",
    "resolved to",
    "waiting for locator",
    "element is not visible",
    "element is not enabled",
    "timeout exceeded while waiting for locator",
)
_ASSERTION_MARKERS = (
    "expect(",
    "assertionerror",
    "tohave",
    "tobevisible",
    "tohavetext",
    "toequal",
    "snapshot",
)
_INFRA_MARKERS = (
    "net::",
    "econnrefused",
    "enotfound",
    "etimedout",
    "err_connection",
    "err_name_not_resolved",
    "socket hang up",
    "browser closed",
    "target closed",
    "protocol error",
    "503",
    "502",
    "504",
)
_DATA_MARKERS = (
    "unique constraint",
    "duplicate key",
    "fixture",
    "test data",
    "seed",
    "not found in database",
)


def _haystack(error: str) -> str:
    return (error or "").strip().lower()


def classify_error(error: str) -> str:
    text = _haystack(error)
    if not text:
        return "unknown"
    if any(m in text for m in _SELECTOR_MARKERS):
        return "selector"
    if any(m in text for m in _ASSERTION_MARKERS):
        return "assertion"
    if any(m in text for m in _INFRA_MARKERS):
        return "infra"
    if any(m in text for m in _DATA_MARKERS):
        return "data"
    return "unknown"


def classify_history(statuses: list[str], *, last_error: str = "") -> dict[str, Any]:
    """statuses are 'passed' / anything-else (failed, timedOut, skipped)."""
    cleaned = [str(s or "").lower() for s in statuses if s]
    runs = len(cleaned)
    fails = sum(1 for s in cleaned if s not in {"passed", "skipped"})
    passes = sum(1 for s in cleaned if s == "passed")
    error_cat = classify_error(last_error) if last_error else "unknown"

    if runs == 0:
        verdict = "unknown"
    elif fails == 0:
        verdict = "healthy"
    elif passes == 0:
        verdict = "failing" if error_cat in {"unknown", "assertion"} else error_cat
    else:
        verdict = "flaky"

    return {
        "verdict": verdict,
        "category": error_cat if verdict != "healthy" else "healthy",
        "runs": runs,
        "fails": fails,
        "passes": passes,
        "fail_pct": round(100 * fails / runs) if runs else 0,
        "recommend_quarantine": verdict == "flaky" and runs >= 3 and fails >= 2,
    }
