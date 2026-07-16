"""FastAPI routes for the Mission Control dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader

from orchestrator.dashboard import activity, auth, history, jobs, k8s

router = APIRouter()

REFRESH_INTERVAL_MS = 5000
SERVER_STARTED = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
VERSION = "0.1.0"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _overall_status(pods: dict[str, Any], runs: list[dict[str, Any]]) -> str:
    """Compute the banner status: go | degraded | down | offline."""
    last_run_failed = bool(runs) and runs[0].get("failed", 0) > 0

    if not pods.get("available"):
        return "degraded" if last_run_failed else "offline"

    pod_list = pods.get("pods", [])
    unhealthy = [
        p for p in pod_list
        if p["phase"] not in {"Running", "Succeeded"} or (p["total"] and p["ready"] < p["total"])
    ]
    if pod_list and len(unhealthy) == len(pod_list):
        return "down"
    if unhealthy or last_run_failed:
        return "degraded"
    return "go"


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/login", response_class=HTMLResponse)
async def login_page() -> str:
    env = Environment(loader=FileSystemLoader(_repo_root() / "templates"))
    return env.get_template("login.html.j2").render(auth_enabled=auth.enabled())


@router.post("/api/login")
def api_login(payload: dict[str, Any] = Body(...)) -> Response:
    """Sync route on purpose — the failure path sleeps for brute-force damping."""
    import json

    if not auth.enabled():
        return Response(
            content=json.dumps({"ok": True, "note": "auth disabled"}),
            media_type="application/json",
        )
    if not auth.verify_credentials(str(payload.get("username", "")), str(payload.get("password", ""))):
        return Response(
            content=json.dumps({"ok": False, "detail": "invalid username or password"}),
            status_code=401,
            media_type="application/json",
        )
    token, max_age = auth.issue_token(remember=bool(payload.get("remember")))
    response = Response(content=json.dumps({"ok": True}), media_type="application/json")
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/api/logout")
async def api_logout() -> Response:
    import json

    response = Response(content=json.dumps({"ok": True}), media_type="application/json")
    response.delete_cookie(auth.COOKIE_NAME)
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page() -> str:
    env = Environment(loader=FileSystemLoader(_repo_root() / "templates"))
    template = env.get_template("dashboard.html.j2")
    return template.render(refresh_interval_ms=REFRESH_INTERVAL_MS)


@router.get("/api/dashboard/overview")
async def overview() -> dict[str, Any]:
    pods = k8s.list_pods()
    workloads = k8s.get_workloads()
    runs = history.load_runs(limit=30)
    return {
        "status": _overall_status(pods, runs),
        "namespace": pods.get("namespace"),
        "cluster": {"available": pods.get("available", False)},
        "pod_count": len(pods.get("pods", [])),
        "workloads": workloads,
        "latest_run": runs[0] if runs else None,
        "report_available": (_repo_root() / "reports" / "qa-summary.html").is_file(),
        "pdf_available": (_repo_root() / "reports" / "qa-summary.pdf").is_file(),
        "auth": {"enabled": auth.enabled(), "user": auth.username() if auth.enabled() else None},
        "server": {"version": VERSION, "started_at": SERVER_STARTED},
    }


@router.get("/api/dashboard/pods")
async def pods() -> dict[str, Any]:
    return k8s.list_pods()


@router.delete("/api/dashboard/pods/{name}")
async def restart_pod(name: str) -> dict[str, Any]:
    result = k8s.delete_pod(name)
    if result.get("ok"):
        activity.record_job("restart-pod", True, f"pod {name} deleted (controller restarts it)", 0)
    return result


@router.get("/api/dashboard/events")
async def events() -> dict[str, Any]:
    return k8s.recent_events()


@router.get("/api/dashboard/videos")
async def videos(limit: int = Query(60, ge=1, le=300)) -> dict[str, Any]:
    """Recorded test videos, newest first, served from /reports."""
    root = _repo_root() / "reports" / "artifacts" / "videos"
    items: list[dict[str, Any]] = []
    if root.exists():
        for path in root.rglob("*.webm"):
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append(
                {
                    "name": path.stem,
                    "run": path.parent.name,
                    "href": "/reports/" + str(path.relative_to(_repo_root() / "reports")),
                    "size_bytes": stat.st_size,
                    "mtime": stat.st_mtime,
                }
            )
    items.sort(key=lambda v: v["mtime"], reverse=True)
    return {"videos": items[:limit]}


@router.get("/api/dashboard/videos.zip")
async def videos_zip() -> Response:
    """All recorded test videos as one zip download."""
    import io
    import zipfile

    root = _repo_root() / "reports" / "artifacts" / "videos"
    buffer = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        if root.exists():
            for path in sorted(root.rglob("*.webm")):
                zf.write(path, arcname=str(path.relative_to(root)))
                count += 1
    if count == 0:
        raise HTTPException(status_code=404, detail="no videos recorded yet")
    buffer.seek(0)
    return Response(
        content=buffer.read(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="zyvor-qa-videos.zip"'},
    )


@router.get("/api/dashboard/specs")
async def spec_files() -> dict[str, Any]:
    """Markdown spec candidates for the spec-path autocomplete."""
    root = _repo_root()
    specs: list[str] = []
    for pattern in ("prompts/examples/*.md", "docs/specs/*.md", "tests/fixtures/fetched/*.md"):
        specs.extend(str(p.relative_to(root)) for p in sorted(root.glob(pattern)))
    return {"specs": specs[:50]}


@router.get("/api/dashboard/pods/{name}/logs")
async def logs(
    name: str,
    lines: int = Query(100, ge=1, le=1000),
    container: str | None = Query(None),
) -> dict[str, Any]:
    return k8s.pod_logs(name, lines=lines, container=container)


@router.get("/api/dashboard/runs")
async def runs(limit: int = Query(30, ge=1, le=200)) -> dict[str, Any]:
    return {"runs": history.load_runs(limit=limit)}


@router.get("/api/dashboard/tests")
async def tests() -> dict[str, Any]:
    return {"tests": history.test_health()}


@router.get("/api/dashboard/schedules")
async def list_schedules() -> dict[str, Any]:
    from orchestrator.dashboard import scheduler

    return {"schedules": scheduler.listing()}


@router.post("/api/dashboard/schedules", status_code=201)
async def add_schedule(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    from orchestrator.dashboard import scheduler

    kind = str(payload.get("kind", ""))
    interval = int(payload.get("interval_s") or 300)
    params = payload.get("params") or {}
    try:
        jobs._validate(kind, params)  # reuse job validation
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return scheduler.add(kind, params, interval)


@router.delete("/api/dashboard/schedules/{sid}")
async def delete_schedule(sid: str) -> dict[str, Any]:
    from orchestrator.dashboard import scheduler

    return {"removed": scheduler.remove(sid)}


def _job_response(started: bool, state: dict[str, Any]) -> Response:
    import json

    return Response(
        content=json.dumps({"started": started, **state}),
        status_code=202 if started else 409,
        media_type="application/json",
    )


@router.post("/api/dashboard/jobs", status_code=202)
async def start_job(payload: dict[str, Any] = Body(...)) -> Response:
    kind = str(payload.get("kind", ""))
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="params must be an object")
    try:
        started, state = jobs.trigger(kind, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _job_response(started, state)


@router.post("/api/dashboard/jobs/cancel")
async def cancel_job() -> dict[str, Any]:
    return jobs.cancel()


@router.post("/api/dashboard/jobs/rerun", status_code=202)
async def rerun_job() -> Response:
    """Re-trigger the last job with the same kind and params."""
    state = jobs.status()
    kind = state.get("kind")
    params = state.get("params") or {}
    if not kind:
        raise HTTPException(status_code=400, detail="no previous job to rerun")
    try:
        started, new_state = jobs.trigger(kind, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _job_response(started, new_state)


@router.get("/api/dashboard/jobs/report.{fmt}")
async def job_report(fmt: str) -> Response:
    """Download the most recent job's report (csv | html | pdf)."""
    if fmt not in {"csv", "html", "pdf"}:
        raise HTTPException(status_code=404, detail="format must be csv, html, or pdf")
    state = jobs.status()
    result = state.get("result") or {}
    href = (result.get("report") or {}).get(fmt)
    if not href:
        raise HTTPException(status_code=404, detail=f"no {fmt} report for the last job")
    path = _repo_root() / href.lstrip("/")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="report file missing")
    media = {"csv": "text/csv", "html": "text/html", "pdf": "application/pdf"}[fmt]
    return Response(
        content=path.read_bytes(),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="zyvor-qa-report.{fmt}"'},
    )


@router.get("/api/dashboard/jobs/status")
async def jobs_status() -> dict[str, Any]:
    state = jobs.status()
    state["recent"] = activity.recent()
    return state


# Back-compat aliases for the original run trigger API
@router.post("/api/dashboard/run", status_code=202)
async def trigger_run(mode: str = Query("smoke", pattern="^(smoke|full)$")) -> Response:
    started, state = jobs.trigger(mode, {})
    return _job_response(started, state)


@router.get("/api/dashboard/run-status")
async def run_status() -> dict[str, Any]:
    return jobs.status()
