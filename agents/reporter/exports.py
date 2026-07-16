"""Export per-job test results as CSV / HTML / PDF, with errors surfaced."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from agents.reporter.pdf import html_to_pdf


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cases_to_csv(cases: list[dict[str, Any]]) -> str:
    """Flatten result cases into CSV text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["title", "status", "browser", "duration_ms", "error", "console_errors", "network_errors", "video", "trace"]
    )
    for c in cases:
        writer.writerow(
            [
                c.get("title", ""),
                c.get("status", ""),
                c.get("browser", ""),
                c.get("duration_ms", ""),
                (c.get("error") or "").replace("\n", " ").strip(),
                " | ".join(c.get("console_logs", []) or []),
                " | ".join(c.get("network_errors", []) or []),
                c.get("video", "") or "",
                c.get("trace", "") or "",
            ]
        )
    return buffer.getvalue()


def cases_to_html(meta: dict[str, Any], cases: list[dict[str, Any]]) -> str:
    """Render a standalone HTML report for a job's cases."""
    env = Environment(loader=FileSystemLoader(_repo_root() / "templates"))
    template = env.get_template("job-report.html.j2")
    failures = [c for c in cases if c.get("status") != "passed"]
    return template.render(
        meta=meta,
        cases=cases,
        failures=failures,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )


def build_report_bundle(
    kind: str,
    cases: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, str]:
    """Write report.html / report.csv / report.pdf into a PVC-backed job dir.

    Returns a map of format → /reports-relative href. Prunes to the newest 30.
    """
    reports = _repo_root() / "reports" / "jobs"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_dir = reports / f"{stamp}-{kind}"
    job_dir.mkdir(parents=True, exist_ok=True)

    meta = {"kind": kind, **summary}
    (job_dir / "report.csv").write_text(cases_to_csv(cases), encoding="utf-8")
    html = cases_to_html(meta, cases)
    html_path = job_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")

    hrefs = {
        "html": f"/reports/jobs/{job_dir.name}/report.html",
        "csv": f"/reports/jobs/{job_dir.name}/report.csv",
    }

    import os

    if os.environ.get("ENABLE_PDF_REPORT", "true").lower() == "true":
        pdf_path = html_to_pdf(html_path, job_dir / "report.pdf")
        if pdf_path:
            hrefs["pdf"] = f"/reports/jobs/{job_dir.name}/report.pdf"

    # prune: keep the newest 30 job report dirs
    dirs = sorted([d for d in reports.iterdir() if d.is_dir()])
    for stale in dirs[:-30]:
        import shutil

        shutil.rmtree(stale, ignore_errors=True)

    return hrefs
