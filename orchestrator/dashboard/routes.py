"""FastAPI routes for the Mission Control dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader

from orchestrator.dashboard import history, jobs, k8s

router = APIRouter()

REFRESH_INTERVAL_MS = 5000


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
    }


@router.get("/api/dashboard/pods")
async def pods() -> dict[str, Any]:
    return k8s.list_pods()


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


@router.get("/api/dashboard/jobs/status")
async def jobs_status() -> dict[str, Any]:
    return jobs.status()


# Back-compat aliases for the original run trigger API
@router.post("/api/dashboard/run", status_code=202)
async def trigger_run(mode: str = Query("smoke", pattern="^(smoke|full)$")) -> Response:
    started, state = jobs.trigger(mode, {})
    return _job_response(started, state)


@router.get("/api/dashboard/run-status")
async def run_status() -> dict[str, Any]:
    return jobs.status()
