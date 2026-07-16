"""Export per-job test results as CSV / HTML / PDF, with errors surfaced."""

from __future__ import annotations

import csv
import io
import os
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

    if os.environ.get("ENABLE_PDF_REPORT", "true").lower() == "true":
        pdf_path = html_to_pdf(html_path, job_dir / "report.pdf")
        if pdf_path:
            hrefs["pdf"] = f"/reports/jobs/{job_dir.name}/report.pdf"

    _prune(reports, 30)
    return hrefs


def _prune(root: Path, keep: int) -> None:
    import shutil

    for stale in sorted([d for d in root.iterdir() if d.is_dir()])[:-keep]:
        shutil.rmtree(stale, ignore_errors=True)


def audit_to_csv(checks: list[str], pages: list[dict[str, Any]]) -> str:
    """Flatten the pages × checks matrix into CSV."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["page", "title", "status"] + [f"{c}_status" for c in checks] + ["issues"])
    for p in pages:
        issues = []
        for c in checks:
            for issue in (p.get("checks", {}).get(c, {}) or {}).get("issues", []):
                issues.append(f"[{c}] {issue}")
        writer.writerow(
            [p.get("path", ""), p.get("title", ""), p.get("status", "")]
            + [(p.get("checks", {}).get(c, {}) or {}).get("status", "-") for c in checks]
            + [" | ".join(issues)]
        )
    return buffer.getvalue()


def build_flow_bundle(url: str, steps: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, str]:
    """Write a flow report (step table + embedded journey video) as HTML/CSV/PDF."""
    reports = _repo_root() / "reports" / "jobs"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_dir = reports / f"{stamp}-flow"
    job_dir.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["step", "action", "description", "status", "error"])
    for s in steps:
        w.writerow([s.get("n"), s.get("action"), s.get("desc"), s.get("status"), (s.get("error") or "").replace("\n", " ")])
    (job_dir / "report.csv").write_text(buf.getvalue(), encoding="utf-8")

    env = Environment(loader=FileSystemLoader(_repo_root() / "templates"))
    html = env.get_template("flow-report.html.j2").render(
        url=url, steps=steps, summary=summary,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    html_path = job_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")

    hrefs = {"html": f"/reports/jobs/{job_dir.name}/report.html", "csv": f"/reports/jobs/{job_dir.name}/report.csv"}
    if os.environ.get("ENABLE_PDF_REPORT", "true").lower() == "true":
        pdf = html_to_pdf(html_path, job_dir / "report.pdf")
        if pdf:
            hrefs["pdf"] = f"/reports/jobs/{job_dir.name}/report.pdf"
    _prune(reports, 30)
    return hrefs


def build_route_sweep_bundle(url: str, rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, str]:
    """Write a route-sweep report (route × viewport matrix + thumbnails) as HTML/CSV/PDF."""
    reports = _repo_root() / "reports" / "jobs"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_dir = reports / f"{stamp}-route-sweep"
    job_dir.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["route", "viewport", "status", "diff_percent"])
    for r in rows:
        w.writerow([r.get("route"), r.get("viewport"), r.get("status"), r.get("diff")])
    (job_dir / "report.csv").write_text(buf.getvalue(), encoding="utf-8")

    env = Environment(loader=FileSystemLoader(_repo_root() / "templates"))
    html = env.get_template("route-sweep-report.html.j2").render(
        url=url, rows=rows, summary=summary,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    html_path = job_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")

    hrefs = {"html": f"/reports/jobs/{job_dir.name}/report.html", "csv": f"/reports/jobs/{job_dir.name}/report.csv"}
    if os.environ.get("ENABLE_PDF_REPORT", "true").lower() == "true":
        pdf = html_to_pdf(html_path, job_dir / "report.pdf")
        if pdf:
            hrefs["pdf"] = f"/reports/jobs/{job_dir.name}/report.pdf"
    _prune(reports, 30)
    return hrefs


def build_audit_bundle(
    url: str, checks: list[str], pages: list[dict[str, Any]], summary: dict[str, Any]
) -> dict[str, str]:
    """Write audit report.html / report.csv / report.pdf into a PVC-backed dir."""
    reports = _repo_root() / "reports" / "jobs"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_dir = reports / f"{stamp}-audit"
    job_dir.mkdir(parents=True, exist_ok=True)

    (job_dir / "report.csv").write_text(audit_to_csv(checks, pages), encoding="utf-8")
    env = Environment(loader=FileSystemLoader(_repo_root() / "templates"))
    html = env.get_template("audit-report.html.j2").render(
        url=url,
        checks=checks,
        pages=pages,
        summary=summary,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    html_path = job_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")

    hrefs = {
        "html": f"/reports/jobs/{job_dir.name}/report.html",
        "csv": f"/reports/jobs/{job_dir.name}/report.csv",
    }
    if os.environ.get("ENABLE_PDF_REPORT", "true").lower() == "true":
        pdf_path = html_to_pdf(html_path, job_dir / "report.pdf")
        if pdf_path:
            hrefs["pdf"] = f"/reports/jobs/{job_dir.name}/report.pdf"

    _prune(reports, 30)
    return hrefs
