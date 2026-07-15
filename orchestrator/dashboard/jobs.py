"""Dashboard job runner — every CLI capability, triggerable online.

Kinds mirror the CLI:
  smoke       zyvor-qa test
  full        zyvor-qa run [--source --spec --pr-number --expand-coverage]
  generate    zyvor-qa generate [--source --spec --expand-coverage]
  discover    zyvor-qa discover
  create      zyvor-qa create "description" [--execute]
  regression  zyvor-qa regression [--update-baselines]

One job at a time; runs on a daemon thread; kind-specific `result` payloads.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

VALID_KINDS = {"smoke", "full", "generate", "discover", "create", "regression"}

_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "kind": None,
    "params": {},
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def status() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def _safe_local_spec(spec: str) -> str:
    """Resolve a local spec path strictly inside the repo — the trigger is
    network-reachable and must not read arbitrary host files."""
    root = _repo_root().resolve()
    candidate = (root / spec).resolve() if not os.path.isabs(spec) else Path(spec).resolve()
    if not str(candidate).startswith(str(root) + os.sep):
        raise ValueError("spec path must be inside the repository")
    if not candidate.is_file():
        raise ValueError(f"spec not found: {spec}")
    return str(candidate)


def _validate(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate params up-front (raises ValueError → HTTP 400)."""
    if kind not in VALID_KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    clean: dict[str, Any] = {}
    if kind in {"full", "generate", "discover"}:
        source = str(params.get("source") or ("github" if kind == "discover" else "local"))
        if source not in {"local", "github"}:
            raise ValueError("source must be local or github")
        clean["source"] = source
        spec = (params.get("spec") or "").strip()
        if spec and source == "local":
            spec = _safe_local_spec(spec)
        clean["spec"] = spec or None
        clean["expand_coverage"] = bool(params.get("expand_coverage"))
    if kind == "full":
        pr = params.get("pr_number")
        clean["pr_number"] = int(pr) if pr not in (None, "", 0) else None
    if kind == "create":
        description = (params.get("description") or "").strip()
        if not description:
            raise ValueError("description is required")
        clean["description"] = description[:500]
        clean["execute"] = bool(params.get("execute"))
    if kind == "regression":
        clean["update_baselines"] = bool(params.get("update_baselines"))
    return clean


def trigger(kind: str, params: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any]]:
    """Start a job unless one is already running. Returns (started, status)."""
    clean = _validate(kind, params or {})
    with _lock:
        if _state["running"]:
            return False, dict(_state)
        _state.update(
            running=True,
            kind=kind,
            params=clean,
            started_at=_now(),
            finished_at=None,
            result=None,
            error=None,
        )
    threading.Thread(target=_run, args=(kind, clean), daemon=True).start()
    return True, status()


def _run(kind: str, params: dict[str, Any]) -> None:
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    try:
        result = _JOBS[kind](params)
    except Exception as exc:  # surfaced in status, never crashes the server
        error = str(exc)
    with _lock:
        _state.update(running=False, finished_at=_now(), result=result, error=error)


# ── job implementations ──────────────────────────────────────────────


def _require_llm() -> None:
    from agents.parser.agent import _llm_available

    if not _llm_available():
        raise RuntimeError(
            "LLM not configured — set LLM_PROVIDER and the matching API key "
            "(e.g. OPENAI_API_KEY) in the environment/secret"
        )


def _report_href() -> Optional[str]:
    return "/reports/qa-summary.html" if (_repo_root() / "reports" / "qa-summary.html").is_file() else None


def _job_smoke(params: dict[str, Any]) -> dict[str, Any]:
    from agents.common.models import PipelineReport
    from agents.execution.runner import run_playwright
    from agents.reporter.agent import generate_summary_stub
    from orchestrator.dashboard import history

    results = run_playwright(
        test_dirs=[str(_repo_root() / "tests" / "manual")],
        base_url=os.environ.get("ZYVOR_BASE_URL", "https://zyvor.dev"),
    )
    report = PipelineReport(
        summary=generate_summary_stub(results),
        passed=results.passed,
        failed=results.failed,
        total=results.total,
    )
    history.append_run(report, source="dashboard-smoke")
    return {"passed": results.passed, "failed": results.failed, "total": results.total}


def _job_full(params: dict[str, Any]) -> dict[str, Any]:
    from orchestrator.cli import _initial_state
    from orchestrator.graph import get_compiled_graph

    state = _initial_state(
        source=params["source"],
        spec=params.get("spec"),
        pr_number=params.get("pr_number"),
        expand_coverage=params.get("expand_coverage", False),
    )
    state["metadata"]["event"] = "dashboard-trigger"
    result = get_compiled_graph().invoke(state)  # report node appends history
    tr = result.get("test_results")
    if result.get("error") and not tr:
        raise RuntimeError(result["error"])
    return {
        "passed": tr.passed if tr else 0,
        "failed": tr.failed if tr else 0,
        "total": tr.total if tr else 0,
        "generated": [Path(p).name for p in result.get("generated_tests", [])],
        "report": _report_href(),
    }


def _generate_states(params: dict[str, Any]):
    """fetch → discover → gap_analyze → parse pipeline prefix, like the CLI."""
    from orchestrator.cli import _initial_state
    from orchestrator.nodes.discover import discover_coverage
    from orchestrator.nodes.fetch import fetch_requirements
    from orchestrator.nodes.gap_analyze import gap_analyze

    state = _initial_state(
        source=params["source"],
        spec=params.get("spec"),
        expand_coverage=params.get("expand_coverage", False),
    )
    state = fetch_requirements(state)
    if state.get("error"):
        raise RuntimeError(state["error"])
    state = discover_coverage(state)
    return gap_analyze(state)


def _job_generate(params: dict[str, Any]) -> dict[str, Any]:
    from orchestrator.nodes.generate import generate_tests
    from orchestrator.nodes.parse import parse_requirements

    state = _generate_states(params)
    state = parse_requirements(state)
    if state.get("error"):
        raise RuntimeError(state["error"])
    state = generate_tests(state)
    metadata = state.get("metadata", {})
    return {
        "generated": [Path(p).name for p in state.get("generated_tests", [])],
        "requirements": len(state.get("requirements", [])),
        "coverage_candidates": metadata.get("coverage_inventory_size"),
        "coverage_gaps": metadata.get("coverage_gaps_remaining"),
        "quality_passed": metadata.get("quality_passed"),
        "quality_regenerated": metadata.get("quality_regenerated"),
    }


def _job_discover(params: dict[str, Any]) -> dict[str, Any]:
    params = {**params, "expand_coverage": True}
    state = _generate_states(params)
    gaps = state.get("coverage_gaps", [])
    return {
        "inventory": len(state.get("coverage_inventory", [])),
        "files_scanned": len(state.get("metadata", {}).get("discovered_paths", [])),
        "gaps": [
            {
                "kind": g.candidate.kind,
                "path": g.candidate.path,
                "title": g.candidate.title,
                "priority": g.candidate.priority,
            }
            for g in gaps[:50]
        ],
        "gaps_total": len(gaps),
    }


def _job_create(params: dict[str, Any]) -> dict[str, Any]:
    _require_llm()
    from agents.nl_create.agent import create_and_generate, create_from_natural_language
    from agents.parser.agent import save_requirements

    root = _repo_root()
    parsed = create_from_natural_language(params["description"])
    save_requirements(parsed, root / "tests" / "fixtures" / "requirements.json")
    generated = create_and_generate(params["description"], str(root / "tests" / "generated"))
    result: dict[str, Any] = {"generated": [Path(p).name for p in generated]}

    if params.get("execute"):
        from agents.common.models import PipelineReport
        from agents.execution.runner import run_playwright
        from agents.reporter.agent import generate_summary_stub
        from orchestrator.dashboard import history

        results = run_playwright(test_dirs=generated)
        report = PipelineReport(
            summary=generate_summary_stub(results),
            passed=results.passed,
            failed=results.failed,
            total=results.total,
        )
        history.append_run(report, source="dashboard-create")
        result.update(passed=results.passed, failed=results.failed, total=results.total)
    return result


def _job_regression(params: dict[str, Any]) -> dict[str, Any]:
    from agents.execution.runner import run_playwright
    from orchestrator.nodes.regression import regression_check

    saved = {k: os.environ.get(k) for k in ("ENABLE_REGRESSION", "UPDATE_BASELINES")}
    os.environ["ENABLE_REGRESSION"] = "true"
    os.environ["UPDATE_BASELINES"] = "true" if params.get("update_baselines") else "false"
    try:
        results = run_playwright(
            test_dirs=[str(_repo_root() / "tests" / "manual")],
            base_url=os.environ.get("ZYVOR_BASE_URL", "https://zyvor.dev"),
        )
        state = regression_check({"test_results": results})
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    diffs = [d.model_dump() for d in state.get("regression_diffs", [])]
    screenshots_root = _repo_root() / "screenshots"
    for d in diffs:
        path = d.get("diff_image_path")
        d["diff_href"] = None
        if path:
            try:
                d["diff_href"] = "/screenshots/" + str(Path(path).relative_to(screenshots_root))
            except ValueError:
                pass
    return {
        "passed": results.passed,
        "failed": results.failed,
        "diffs": diffs,
        "baselines_updated": params.get("update_baselines", False),
    }


_JOBS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "smoke": _job_smoke,
    "full": _job_full,
    "generate": _job_generate,
    "discover": _job_discover,
    "create": _job_create,
    "regression": _job_regression,
}
