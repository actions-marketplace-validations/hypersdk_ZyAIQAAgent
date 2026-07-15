"""Persist and load QA run history for the dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.common.models import PipelineReport

MAX_HISTORY_FILES = 200


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _history_dir() -> Path:
    return _repo_root() / "reports" / "history"


def append_run(report: PipelineReport, *, source: str = "local") -> Path:
    """Write one history entry for a completed pipeline run."""
    history_dir = _history_dir()
    history_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc)
    entry = {
        "timestamp": timestamp.isoformat(),
        "source": source,
        **report.model_dump(),
    }

    path = history_dir / f"run-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    _prune(history_dir)
    return path


def _prune(history_dir: Path) -> None:
    files = sorted(history_dir.glob("run-*.json"))
    for stale in files[:-MAX_HISTORY_FILES]:
        try:
            stale.unlink()
        except OSError:
            continue


def load_runs(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent runs, newest first."""
    history_dir = _history_dir()
    if not history_dir.exists():
        return []

    runs: list[dict[str, Any]] = []
    for path in sorted(history_dir.glob("run-*.json"), reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        runs.append(
            {
                "timestamp": data.get("timestamp"),
                "source": data.get("source", "unknown"),
                "passed": data.get("passed", 0),
                "failed": data.get("failed", 0),
                "total": data.get("total", 0),
                "summary": (data.get("summary") or "")[:300],
                "v8_coverage_percentage": data.get("v8_coverage_percentage"),
            }
        )
    return runs
