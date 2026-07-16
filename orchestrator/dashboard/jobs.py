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

VALID_KINDS = {"smoke", "full", "generate", "discover", "create", "regression", "crawl_test"}

_lock = threading.Lock()
_cancel = threading.Event()
_progress: list[str] = []
_live_cases: list[dict[str, Any]] = []
_state: dict[str, Any] = {
    "running": False,
    "kind": None,
    "params": {},
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


class JobCancelled(Exception):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_progress(message: str) -> None:
    """Append a stage line visible live in the dashboard's job panel."""
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    with _lock:
        _progress.append(f"[{stamp}] {message}")
        del _progress[:-200]


def _check_cancel() -> None:
    if _cancel.is_set():
        raise JobCancelled("cancelled by user")


def _stream_line(line: str) -> None:
    """Feed a Playwright stdout line into the live log and per-test tally."""
    import re

    log_progress(line)
    m = re.match(r"^\s*(✓|✗|✘|×)\s+\d+\s+(?:\[([^\]]+)\]\s+)?›?\s*(.+?)(?:\s+\(([\d.]+m?s)\))?\s*$", line)
    if not m:
        return
    mark, browser, title = m.group(1), m.group(2), m.group(3)
    status = "passed" if mark == "✓" else "failed"
    with _lock:
        _live_cases.append({"title": title.strip()[:120], "status": status, "browser": browser})


def cancel() -> dict[str, Any]:
    """Request cancellation of the running job (kills an in-flight Playwright run)."""
    with _lock:
        running = _state["running"]
    if running:
        _cancel.set()
        log_progress("⏹ cancellation requested…")
        try:
            from agents.execution.runner import terminate_current

            if terminate_current():
                log_progress("terminated in-flight Playwright process")
        except Exception:
            pass
    return status()


def status() -> dict[str, Any]:
    with _lock:
        state = dict(_state)
        state["progress"] = _progress[-80:]
        state["live_cases"] = list(_live_cases)
        state["live_tally"] = {
            "passed": sum(1 for c in _live_cases if c["status"] == "passed"),
            "failed": sum(1 for c in _live_cases if c["status"] != "passed"),
        }
    return state


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
    if kind == "crawl_test":
        url = (params.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        clean["url"] = url[:500]
        clean["username"] = (params.get("username") or "").strip()[:200]
        clean["password"] = (params.get("password") or "")[:200]
        clean["insecure"] = bool(params.get("insecure"))
        max_pages = int(params.get("max_pages") or 30)
        clean["max_pages"] = max(1, min(max_pages, 200))
    return clean


def trigger(kind: str, params: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any]]:
    """Start a job unless one is already running. Returns (started, status)."""
    clean = _validate(kind, params or {})
    with _lock:
        if _state["running"]:
            return False, dict(_state)
        _cancel.clear()
        _progress.clear()
        _live_cases.clear()
        _state.update(
            running=True,
            kind=kind,
            params=clean,
            started_at=_now(),
            finished_at=None,
            result=None,
            error=None,
        )
    log_progress(f"▶ {kind} started")
    threading.Thread(target=_run, args=(kind, clean), daemon=True).start()
    return True, status()


def _brief(kind: str, result: Optional[dict[str, Any]], error: Optional[str]) -> str:
    if error:
        return error
    r = result or {}
    if "total" in r and r.get("total") is not None:
        return f"{r.get('passed', 0)}/{r.get('total', 0)} passed"
    if kind == "discover":
        return f"{r.get('inventory', 0)} candidates, {r.get('gaps_total', 0)} gaps"
    if "generated" in r:
        return f"{len(r['generated'])} test file(s) generated"
    if kind == "regression":
        return f"{len(r.get('diffs', []))} screenshot(s) compared"
    return "done"


def _run(kind: str, params: dict[str, Any]) -> None:
    import time as _time

    from orchestrator.dashboard import activity

    t0 = _time.time()
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    try:
        result = _JOBS[kind](params)
        log_progress(f"✅ {kind} finished: {_brief(kind, result, None)}")
    except JobCancelled:
        error = "cancelled by user"
        log_progress("⏹ job cancelled")
    except Exception as exc:  # surfaced in status, never crashes the server
        error = str(exc)
        log_progress(f"❌ {kind} failed: {error}")
    duration = _time.time() - t0
    with _lock:
        _state.update(running=False, finished_at=_now(), result=result, error=error)
    activity.record_job(kind, error is None, _brief(kind, result, error), duration)


# ── job implementations ──────────────────────────────────────────────


def _require_llm() -> None:
    from agents.parser.agent import _llm_available

    if not _llm_available():
        raise RuntimeError(
            "LLM not configured — set LLM_PROVIDER and the matching API key "
            "(e.g. OPENAI_API_KEY) in the environment/secret"
        )


def _slug(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "test"


def _persist_artifacts(results: Any, kind: str) -> tuple[dict[str, str], dict[str, str]]:
    """Copy every test video + trace into the PVC-backed reports tree.
    Returns (title→video href, title→trace href)."""
    import shutil

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    videos: dict[str, str] = {}
    traces: dict[str, str] = {}
    for case in results.cases:
        for kind_name, path_attr, ext, sink in (
            ("videos", "video_path", "webm", videos),
            ("traces", "trace_path", "zip", traces),
        ):
            src_val = getattr(case, path_attr, None)
            if not src_val:
                continue
            src = Path(src_val)
            if not src.exists():
                continue
            rel_dir = f"artifacts/{kind_name}/{stamp}-{kind}"
            dest = _repo_root() / "reports" / rel_dir
            dest.mkdir(parents=True, exist_ok=True)
            name = f"{_slug(case.title)}.{ext}"
            try:
                shutil.copy2(src, dest / name)
            except OSError:
                continue
            sink[case.title] = f"/reports/{rel_dir}/{name}"
    if videos:
        log_progress(f"saved {len(videos)} test video(s)")
    if traces:
        log_progress(f"saved {len(traces)} trace(s)")
    # keep the libraries bounded: newest 20 run-directories each
    for kind_name in ("videos", "traces"):
        root = _repo_root() / "reports" / "artifacts" / kind_name
        if root.exists():
            for stale in sorted([d for d in root.iterdir() if d.is_dir()])[:-20]:
                shutil.rmtree(stale, ignore_errors=True)
    return videos, traces


# back-compat: some callers still expect the video-only helper
def _persist_videos(results: Any, kind: str) -> dict[str, str]:
    return _persist_artifacts(results, kind)[0]


def _cases_payload(
    results: Any,
    limit: int = 60,
    videos: dict[str, str] | None = None,
    traces: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Full per-test detail for the result tables and downloadable reports."""
    return [
        {
            "title": c.title[:120],
            "status": c.status,
            "browser": c.browser,
            "duration_ms": round(c.duration_ms or 0),
            "error": (c.error_message or "")[:1200] if c.status != "passed" else "",
            "console_logs": [line for line in (c.console_logs or []) if line.startswith("[error]")][:8],
            "network_errors": (c.network_errors or [])[:8],
            "video": (videos or {}).get(c.title),
            "trace": (traces or {}).get(c.title),
        }
        for c in results.cases[:limit]
    ]


def _finalize(kind: str, results: Any, videos, traces, duration_s: float | None = None) -> dict[str, Any]:
    """Build the case list + a downloadable CSV/HTML/PDF report bundle."""
    cases = _cases_payload(results, videos=videos, traces=traces)
    report: dict[str, str] = {}
    try:
        from agents.reporter.exports import build_report_bundle

        log_progress("building CSV / HTML / PDF report…")
        report = build_report_bundle(
            kind,
            cases,
            {
                "passed": results.passed,
                "failed": results.failed,
                "total": results.total,
                "duration_s": round(duration_s, 1) if duration_s is not None else None,
                "target": os.environ.get("ZYVOR_BASE_URL"),
            },
        )
    except Exception as exc:
        log_progress(f"report bundle failed: {str(exc)[:80]}")
    return {"cases": cases, "report": report}


def _report_href() -> Optional[str]:
    return "/reports/qa-summary.html" if (_repo_root() / "reports" / "qa-summary.html").is_file() else None


def _job_smoke(params: dict[str, Any]) -> dict[str, Any]:
    import time as _time

    from agents.common.models import PipelineReport
    from agents.execution.runner import run_playwright
    from agents.reporter.agent import generate_summary_stub
    from orchestrator.dashboard import history

    t0 = _time.time()
    base_url = os.environ.get("ZYVOR_BASE_URL", "https://zyvor.dev")
    log_progress(f"running tests/manual against {base_url} (Playwright + Chromium, video on)…")
    with _env_overrides({"ZYVOR_VIDEO": "on"}):
        results = run_playwright(
            test_dirs=[str(_repo_root() / "tests" / "manual")],
            base_url=base_url,
            on_line=_stream_line,
        )
    _check_cancel()
    log_progress(f"execution done: {results.passed}/{results.total} passed")
    videos, traces = _persist_artifacts(results, "smoke")
    final = _finalize("smoke", results, videos, traces, duration_s=_time.time() - t0)
    report = PipelineReport(
        summary=generate_summary_stub(results),
        passed=results.passed,
        failed=results.failed,
        total=results.total,
    )
    history.append_run(report, source="dashboard-smoke", duration_s=_time.time() - t0)
    return {
        "passed": results.passed,
        "failed": results.failed,
        "total": results.total,
        **final,
    }


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
    log_progress(f"full pipeline: fetch → parse → generate → execute → report (source={params['source']})")
    result = get_compiled_graph().invoke(state)  # report node appends history
    _check_cancel()
    tr = result.get("test_results")
    log_progress("pipeline graph finished")
    if result.get("error") and not tr:
        raise RuntimeError(result["error"])
    return {
        "passed": tr.passed if tr else 0,
        "failed": tr.failed if tr else 0,
        "total": tr.total if tr else 0,
        "generated": [Path(p).name for p in result.get("generated_tests", [])],
        **(_finalize("full", tr, {}, {}) if tr else {"cases": [], "report": {}}),
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
    log_progress(f"fetching specs (source={params['source']})…")
    state = fetch_requirements(state)
    if state.get("error"):
        raise RuntimeError(state["error"])
    _check_cancel()
    log_progress("discovering coverage candidates…")
    state = discover_coverage(state)
    return gap_analyze(state)


def _job_generate(params: dict[str, Any]) -> dict[str, Any]:
    from orchestrator.nodes.generate import generate_tests
    from orchestrator.nodes.parse import parse_requirements

    state = _generate_states(params)
    _check_cancel()
    log_progress("parsing requirements…")
    state = parse_requirements(state)
    if state.get("error"):
        raise RuntimeError(state["error"])
    _check_cancel()
    log_progress(f"generating tests for {len(state.get('requirements', []))} requirement(s)…")
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
    from agents.generator.agent import generate_tests_from_requirements
    from agents.nl_create.agent import (
        create_from_natural_language,
        create_from_natural_language_heuristic,
    )
    from agents.parser.agent import _llm_available, save_requirements

    root = _repo_root()
    mode = "llm"
    if _llm_available():
        log_progress("asking the LLM to turn the description into requirements…")
        try:
            parsed = create_from_natural_language(params["description"])
        except Exception as exc:
            log_progress(f"LLM failed ({str(exc)[:80]}) — falling back to heuristic parsing")
            parsed = create_from_natural_language_heuristic(params["description"])
            mode = "heuristic"
    else:
        log_progress("no LLM key configured — using heuristic parsing")
        parsed = create_from_natural_language_heuristic(params["description"])
        mode = "heuristic"

    save_requirements(parsed, root / "tests" / "fixtures" / "requirements.json")
    log_progress(f"generating Playwright test(s) from {len(parsed.requirements)} requirement(s)…")
    generated, _stats = generate_tests_from_requirements(
        parsed.requirements, root / "tests" / "generated"
    )
    result: dict[str, Any] = {"generated": [Path(p).name for p in generated], "mode": mode}

    if params.get("execute"):
        import time as _time

        from agents.common.models import PipelineReport
        from agents.execution.runner import run_playwright
        from agents.reporter.agent import generate_summary_stub
        from orchestrator.dashboard import history

        t0 = _time.time()
        log_progress(f"executing {len(generated)} generated test(s) (video on)…")
        with _env_overrides({"ZYVOR_VIDEO": "on"}):
            results = run_playwright(test_dirs=generated, on_line=_stream_line)
        _check_cancel()
        videos, traces = _persist_artifacts(results, "create")
        report = PipelineReport(
            summary=generate_summary_stub(results),
            passed=results.passed,
            failed=results.failed,
            total=results.total,
        )
        history.append_run(report, source="dashboard-create", duration_s=_time.time() - t0)
        result.update(
            passed=results.passed,
            failed=results.failed,
            total=results.total,
            **_finalize("create", results, videos, traces, duration_s=_time.time() - t0),
        )
    return result


def _job_regression(params: dict[str, Any]) -> dict[str, Any]:
    from agents.execution.runner import run_playwright
    from orchestrator.nodes.regression import regression_check

    saved = {k: os.environ.get(k) for k in ("ENABLE_REGRESSION", "UPDATE_BASELINES")}
    os.environ["ENABLE_REGRESSION"] = "true"
    os.environ["UPDATE_BASELINES"] = "true" if params.get("update_baselines") else "false"
    try:
        log_progress("running manual suite with screenshot capture…")
        results = run_playwright(
            test_dirs=[str(_repo_root() / "tests" / "manual")],
            base_url=os.environ.get("ZYVOR_BASE_URL", "https://zyvor.dev"),
            on_line=_stream_line,
        )
        _check_cancel()
        log_progress("comparing screenshots against baselines…")
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


def _env_overrides(overrides: dict[str, Optional[str]]):
    """Context manager: apply env overrides for a job, restore afterwards."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        saved = {k: os.environ.get(k) for k in overrides}
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    return _ctx()


def _job_crawl_test(params: dict[str, Any]) -> dict[str, Any]:
    """Point the agent at ANY site: crawl every reachable page, generate a test
    per page, run them all. Self-signed TLS and target login supported."""
    from agents.common.models import CoverageGap, PipelineReport
    from agents.coverage.gap import gaps_to_requirements
    from agents.discover.crawl import crawl_live_site
    from agents.execution.runner import run_playwright
    from agents.generator.agent import generate_tests_from_requirements
    from agents.reporter.agent import generate_summary_stub
    from orchestrator.dashboard import history

    url = params["url"]
    overrides: dict[str, Optional[str]] = {
        "ZYVOR_BASE_URL": url,
        "ENABLE_LIVE_CRAWL": "true",
        "CRAWL_MAX_PAGES": str(params["max_pages"]),
        "ZYVOR_IGNORE_HTTPS_ERRORS": "true" if params.get("insecure") else None,
        "ZYVOR_TEST_USER": params.get("username") or None,
        "ZYVOR_TEST_PASSWORD": params.get("password") or None,
        # target is arbitrary — don't treat it as the zyvor.dev marketing site
        "ENABLE_DASHBOARD_TESTS": "true" if params.get("username") else None,
    }

    import time as _time

    t0 = _time.time()
    with _env_overrides(overrides):
        log_progress(f"crawling {url} (max {params['max_pages']} pages, BFS)…")
        candidates = crawl_live_site(url)
        if not candidates:
            raise RuntimeError(f"crawl found no reachable pages at {url}")
        _check_cancel()
        log_progress(f"found {len(candidates)} page(s): " + ", ".join(c.path for c in candidates[:8]) + ("…" if len(candidates) > 8 else ""))

        requirements = gaps_to_requirements([CoverageGap(candidate=c) for c in candidates])
        output_dir = _repo_root() / "tests" / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)
        log_progress(f"generating {len(requirements)} validation test(s)…")
        generated, _stats = generate_tests_from_requirements(
            requirements, output_dir, coverage_mode=True
        )
        _check_cancel()
        log_progress(f"executing {len(generated)} test(s) with Playwright (video on)…")
        with _env_overrides({"ZYVOR_VIDEO": "on"}):
            results = run_playwright(test_dirs=generated, base_url=url, on_line=_stream_line)
        _check_cancel()
        log_progress(f"execution done: {results.passed}/{results.total} passed")
        videos, traces = _persist_artifacts(results, "crawl")

    report = PipelineReport(
        summary=f"Crawl of {url}: {results.passed}/{results.total} pages passed. "
        + generate_summary_stub(results),
        passed=results.passed,
        failed=results.failed,
        total=results.total,
    )
    history.append_run(report, source="dashboard-crawl", duration_s=_time.time() - t0)
    return {
        "url": url,
        "pages_found": len(candidates),
        "generated": [Path(p).name for p in generated],
        "passed": results.passed,
        "failed": results.failed,
        "total": results.total,
        **_finalize("crawl", results, videos, traces),
    }


_JOBS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "smoke": _job_smoke,
    "full": _job_full,
    "generate": _job_generate,
    "discover": _job_discover,
    "create": _job_create,
    "regression": _job_regression,
    "crawl_test": _job_crawl_test,
}
