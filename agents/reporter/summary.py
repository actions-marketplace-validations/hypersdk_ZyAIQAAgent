# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Write reports/summary.json — the stable, CI-facing result contract.

External CI systems (GitHub Actions, GitLab, CircleCI, Jenkins, Azure
Pipelines) need one small machine-readable file to gate on, independent of
Playwright's own reporter schema. This is that file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


def _repo_root() -> Path:
    from orchestrator.paths import repo_root

    return repo_root()


def write_ci_summary(
    *,
    command: str,
    target_url: str | None,
    passed: int,
    failed: int,
    total: int,
    exit_code: int,
    started_at: str,
    duration_s: float,
    skipped: int = 0,
    artifacts: dict[str, str | None] | None = None,
    extra: dict[str, Any] | None = None,
    findings_by_severity: dict[str, int] | None = None,
    max_severity: str | None = None,
) -> Path:
    """Write reports/summary.json and return its path.

    `findings_by_severity`/`max_severity` are optional — only commands that
    raise findings (audit, misconfig_scan, cve_lookup, llm_redteam) populate
    them; `argus <group> <cmd> --fail-on <severity>` reads `max_severity` back to
    decide whether to exit non-zero.
    """
    summary = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "target_url": target_url,
        "started_at": started_at,
        "duration_s": round(duration_s, 3),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "exit_code": exit_code,
        "status": "passed" if failed == 0 and exit_code == 0 else "failed",
        "artifacts": artifacts or {},
        "findings_by_severity": findings_by_severity or {},
        "max_severity": max_severity,
        "extra": extra or {},
    }
    reports_dir = _repo_root() / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path
