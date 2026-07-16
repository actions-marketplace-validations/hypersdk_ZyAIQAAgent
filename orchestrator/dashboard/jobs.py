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

VALID_KINDS = {
    "smoke", "full", "generate", "discover", "create", "regression",
    "crawl_test", "audit", "flaky", "screenshot", "compare", "ping",
    "loadtest", "tls",
}

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


def _stream_line_audit(line: str) -> None:
    """Audit progress line → live log + one live-case per audited page."""
    import re

    log_progress(line)
    m = re.match(r"^audit:\s+(\S+)\s+\((?:HTTP\s+)?(\d+)\)", line)
    if not m:
        return
    path_, status = m.group(1), int(m.group(2))
    with _lock:
        _live_cases.append(
            {"title": path_, "status": "passed" if 200 <= status < 400 else "failed", "browser": None}
        )


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
    if kind == "audit":
        url = (params.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        clean["url"] = url[:500]
        clean["max_pages"] = max(1, min(int(params.get("max_pages") or 10), 100))
        selected = params.get("checks") or ["a11y", "links", "seo", "console", "perf", "headers"]
        from agents.audit.engine import VALID_CHECKS

        clean["checks"] = [c for c in selected if c in VALID_CHECKS] or ["a11y", "seo", "console"]
        clean["username"] = (params.get("username") or "").strip()[:200]
        clean["password"] = (params.get("password") or "")[:200]
        clean["insecure"] = bool(params.get("insecure"))
    if kind == "flaky":
        clean["runs"] = max(2, min(int(params.get("runs") or 3), 10))
        target = (params.get("target") or "manual").strip()
        if target != "manual":
            target = _safe_local_spec(target)
        clean["target"] = target
    if kind == "screenshot":
        url = (params.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        clean["url"] = url[:500]
        vps = params.get("viewports") or ["desktop"]
        clean["viewports"] = [v for v in vps if v in ("desktop", "tablet", "mobile")] or ["desktop"]
        clean["full_page"] = bool(params.get("full_page"))
        clean["insecure"] = bool(params.get("insecure"))
    if kind == "compare":
        for key in ("url_a", "url_b"):
            u = (params.get(key) or "").strip()
            if not u.startswith(("http://", "https://")):
                raise ValueError(f"{key} must start with http:// or https://")
            clean[key] = u[:500]
        clean["insecure"] = bool(params.get("insecure"))
    if kind == "ping":
        raw = params.get("urls") or ""
        if isinstance(raw, str):
            raw = raw.replace(",", "\n").split("\n")
        urls = [u.strip() for u in raw if u.strip().startswith(("http://", "https://"))]
        if not urls:
            raise ValueError("provide at least one http(s) URL")
        clean["urls"] = urls[:30]
    if kind == "loadtest":
        url = (params.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        clean["url"] = url[:500]
        clean["requests"] = max(10, min(int(params.get("requests") or 100), 1000))
        clean["concurrency"] = max(1, min(int(params.get("concurrency") or 10), 50))
    if kind == "tls":
        host = (params.get("host") or "").strip()
        if host.startswith(("http://", "https://")):
            from urllib.parse import urlparse

            host = urlparse(host).hostname or ""
        if not host or "/" in host or " " in host:
            raise ValueError("provide a hostname, e.g. zyvor.dev")
        clean["host"] = host[:255]
        clean["port"] = max(1, min(int(params.get("port") or 443), 65535))
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


def _explain_failure(error: str) -> str:
    """Heuristic likely-cause hint for a Playwright failure (no LLM needed)."""
    e = (error or "").lower()
    if not e:
        return ""
    if "timeout" in e and ("locator" in e or "waiting for" in e or "getby" in e):
        return "Element never appeared — selector may have changed, or the page loaded too slowly."
    if "timeout" in e and ("goto" in e or "navigation" in e):
        return "Navigation timed out — the target may be down, slow, or blocking the request."
    if "strict mode violation" in e or "resolved to" in e:
        return "Selector matched multiple elements — make it more specific (add a role or exact text)."
    if "tobevisible" in e or "not visible" in e:
        return "Element exists but isn't visible — it may be hidden, off-screen, or behind an overlay."
    if "expected" in e and "received" in e:
        return "Assertion mismatch — the actual text/value differs from what the test expects."
    if "net::" in e or "err_" in e or "econnrefused" in e:
        return "Network error reaching the target — check the URL, TLS, or that the service is up."
    if "no valid playwright spec" in e:
        return "The generated spec had a syntax error and was skipped — regenerate it."
    return "Review the trace or video to see the exact step that failed."


def _cases_payload(
    results: Any,
    limit: int = 60,
    videos: dict[str, str] | None = None,
    traces: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Full per-test detail for the result tables and downloadable reports."""
    payload = []
    for c in results.cases[:limit]:
        error = (c.error_message or "")[:1200] if c.status != "passed" else ""
        payload.append(
            {
                "title": c.title[:120],
                "status": c.status,
                "browser": c.browser,
                "duration_ms": round(c.duration_ms or 0),
                "error": error,
                "hint": _explain_failure(error) if error else "",
                "console_logs": [line for line in (c.console_logs or []) if line.startswith("[error]")][:8],
                "network_errors": (c.network_errors or [])[:8],
                "video": (videos or {}).get(c.title),
                "trace": (traces or {}).get(c.title),
            }
        )
    return payload


def _finalize(kind: str, results: Any, videos, traces, duration_s: float | None = None) -> dict[str, Any]:
    """Build the case list + a downloadable CSV/HTML/PDF report bundle."""
    cases = _cases_payload(results, videos=videos, traces=traces)
    try:
        from orchestrator.dashboard import history

        history.record_test_results(cases)
    except Exception:
        pass
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


def _job_audit(params: dict[str, Any]) -> dict[str, Any]:
    """Crawl a site and run per-page QA checks (a11y / links / SEO / perf / …)."""
    import time as _time

    from agents.audit.engine import run_audit
    from agents.common.models import PipelineReport
    from agents.reporter.exports import build_audit_bundle
    from orchestrator.dashboard import history

    t0 = _time.time()
    url = params["url"]
    checks = params["checks"]
    log_progress(f"auditing {url} — checks: {', '.join(checks)} (max {params['max_pages']} pages)")
    data = run_audit(
        url,
        checks,
        max_pages=params["max_pages"],
        insecure=params.get("insecure", False),
        username=params.get("username", ""),
        password=params.get("password", ""),
        on_line=_stream_line_audit,
    )
    _check_cancel()
    pages = data.get("pages", [])
    summary = data.get("summary", {})
    by_check = summary.get("byCheck", {})
    total_fail = sum(v.get("fail", 0) for v in by_check.values())
    total_warn = sum(v.get("warn", 0) for v in by_check.values())
    log_progress(f"audit done: {len(pages)} pages, {total_fail} failing checks, {total_warn} warnings")

    # aggregate a health grade (A–F) — weighted pass ratio across all checks
    weights = {"a11y": 3, "console": 2, "links": 2, "seo": 1, "perf": 1, "headers": 1, "responsive": 1}
    earned = possible = 0.0
    for check, counts in by_check.items():
        w = weights.get(check, 1)
        n = sum(counts.values())
        if not n:
            continue
        possible += w * n
        earned += w * (counts.get("ok", 0) + 0.5 * counts.get("warn", 0))
    score = round(100 * earned / possible) if possible else 100
    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    log_progress(f"health grade: {grade} ({score}/100)")

    report = build_audit_bundle(url, checks, pages, summary)

    hist = PipelineReport(
        summary=f"Audit of {url}: {len(pages)} pages, {total_fail} failing / {total_warn} warning checks",
        passed=sum(v.get("ok", 0) for v in by_check.values()),
        failed=total_fail,
        total=sum(sum(v.values()) for v in by_check.values()),
    )
    history.append_run(hist, source="dashboard-audit", duration_s=_time.time() - t0)
    return {
        "url": url,
        "checks": checks,
        "pages_audited": len(pages),
        "by_check": by_check,
        "fail_count": total_fail,
        "warn_count": total_warn,
        "grade": grade,
        "score": score,
        "audit_pages": pages,
        "report": report,
    }


def _job_screenshot(params: dict[str, Any]) -> dict[str, Any]:
    """Capture on-demand full-page screenshots of any URL at chosen viewports."""
    import json as _json
    import subprocess

    url = params["url"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rel_dir = f"artifacts/shots/{stamp}"
    out_dir = _repo_root() / "reports" / rel_dir
    env = {**os.environ, "ZYVOR_BASE_URL": url}
    if params.get("insecure"):
        env["ZYVOR_IGNORE_HTTPS_ERRORS"] = "true"

    log_progress(f"capturing {url} at {', '.join(params['viewports'])}…")
    script = _repo_root() / "playwright" / "scripts" / "shot-url.mjs"
    cmd = [
        "node", str(script), url, str(out_dir),
        ",".join(params["viewports"]),
        "full" if params.get("full_page") else "",
    ]
    proc = subprocess.run(cmd, cwd=_repo_root(), env=env, capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"screenshot failed: {(proc.stderr or '')[:200]}")
    data = _json.loads(proc.stdout)

    # prune older shot dirs
    root = _repo_root() / "reports" / "artifacts" / "shots"
    if root.exists():
        import shutil

        for stale in sorted([d for d in root.iterdir() if d.is_dir()])[:-20]:
            shutil.rmtree(stale, ignore_errors=True)

    shots = [
        {**s, "href": f"/reports/{rel_dir}/{s['file']}"}
        for s in data.get("shots", [])
    ]
    log_progress(f"captured {len(shots)} screenshot(s)")
    return {"url": url, "status": data.get("status"), "title": data.get("title"), "shots": shots}


def _job_flaky(params: dict[str, Any]) -> dict[str, Any]:
    """Run a suite N times and report which tests flake (mixed pass/fail)."""
    import time as _time

    from agents.common.models import PipelineReport
    from agents.execution.runner import run_playwright
    from orchestrator.dashboard import history

    t0 = _time.time()
    runs = params["runs"]
    target = params["target"]
    test_dirs = [str(_repo_root() / "tests" / "manual")] if target == "manual" else [target]
    base_url = os.environ.get("ZYVOR_BASE_URL", "https://zyvor.dev")

    tally: dict[str, dict[str, int]] = {}
    for i in range(runs):
        _check_cancel()
        log_progress(f"flaky run {i + 1}/{runs}…")
        results = run_playwright(test_dirs=test_dirs, base_url=base_url, on_line=_stream_line)
        for c in results.cases:
            rec = tally.setdefault(c.title[:120], {"pass": 0, "fail": 0})
            rec["pass" if c.status == "passed" else "fail"] += 1
        try:
            history.record_test_results(
                [{"title": c.title[:120], "status": c.status} for c in results.cases]
            )
        except Exception:
            pass

    cases = []
    flaky_count = 0
    for title, rec in sorted(tally.items(), key=lambda kv: -(kv[1]["fail"])):
        total = rec["pass"] + rec["fail"]
        is_flaky = rec["pass"] > 0 and rec["fail"] > 0
        if is_flaky:
            flaky_count += 1
        cases.append(
            {
                "title": title,
                "status": "flaky" if is_flaky else ("passed" if rec["fail"] == 0 else "failed"),
                "passes": rec["pass"],
                "runs": total,
                "flake_pct": round(100 * rec["fail"] / total) if total else 0,
            }
        )

    log_progress(f"flaky check done: {flaky_count} flaky test(s) over {runs} runs")
    hist = PipelineReport(
        summary=f"Flaky check ({runs} runs): {flaky_count} flaky of {len(cases)} tests",
        passed=sum(1 for c in cases if c["status"] == "passed"),
        failed=flaky_count,
        total=len(cases),
    )
    history.append_run(hist, source="dashboard-flaky", duration_s=_time.time() - t0)
    return {"runs": runs, "flaky_count": flaky_count, "flaky_cases": cases}


def _capture_one(url: str, out_dir: Path, tag: str, insecure: bool) -> Optional[Path]:
    import json as _json
    import subprocess

    env = {**os.environ, "ZYVOR_BASE_URL": url}
    if insecure:
        env["ZYVOR_IGNORE_HTTPS_ERRORS"] = "true"
    script = _repo_root() / "playwright" / "scripts" / "shot-url.mjs"
    proc = subprocess.run(
        ["node", str(script), url, str(out_dir), "desktop", "full"],
        cwd=_repo_root(), env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    data = _json.loads(proc.stdout)
    shots = data.get("shots", [])
    return (out_dir / shots[0]["file"]) if shots else None


def _job_compare(params: dict[str, Any]) -> dict[str, Any]:
    """Visual-diff two URLs (e.g. staging vs prod) at desktop, full page."""
    import shutil

    from agents.regression.compare_screenshots import _diff_percent

    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("Pillow required for compare")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rel_dir = f"artifacts/compare/{stamp}"
    out_dir = _repo_root() / "reports" / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    log_progress(f"capturing A: {params['url_a']}")
    a = _capture_one(params["url_a"], out_dir, "a", params.get("insecure", False))
    _check_cancel()
    log_progress(f"capturing B: {params['url_b']}")
    b = _capture_one(params["url_b"], out_dir, "b", params.get("insecure", False))
    if not a or not b:
        raise RuntimeError("failed to capture one or both URLs")

    img_a = Image.open(a).convert("RGB")
    img_b = Image.open(b).convert("RGB")
    if img_a.size != img_b.size:
        img_b = img_b.resize(img_a.size)
    from PIL import ImageChops

    diff_img = ImageChops.difference(img_a, img_b)
    diff_path = out_dir / "diff.png"
    diff_img.save(diff_path)
    pct = round(_diff_percent(img_a, img_b), 3)
    log_progress(f"visual difference: {pct}%")

    # prune
    root = _repo_root() / "reports" / "artifacts" / "compare"
    if root.exists():
        for stale in sorted([d for d in root.iterdir() if d.is_dir()])[:-20]:
            shutil.rmtree(stale, ignore_errors=True)

    base = f"/reports/{rel_dir}"
    return {
        "url_a": params["url_a"], "url_b": params["url_b"],
        "diff_percent": pct,
        "identical": pct < 0.1,
        "a_href": f"{base}/{a.name}", "b_href": f"{base}/{b.name}", "diff_href": f"{base}/diff.png",
    }


def _job_ping(params: dict[str, Any]) -> dict[str, Any]:
    """HTTP status + latency check across a list of URLs."""
    import time as _time

    import httpx

    results = []
    up = 0
    with httpx.Client(timeout=15, follow_redirects=True, verify=False) as client:
        for url in params["urls"]:
            _check_cancel()
            t0 = _time.time()
            try:
                resp = client.get(url)
                ms = round((_time.time() - t0) * 1000)
                ok = resp.status_code < 400
                up += 1 if ok else 0
                results.append({"url": url, "status": resp.status_code, "ms": ms, "ok": ok})
                log_progress(f"{resp.status_code} {url} ({ms}ms)")
            except Exception as exc:
                results.append({"url": url, "status": 0, "ms": None, "ok": False, "error": str(exc)[:120]})
                log_progress(f"ERR {url}: {str(exc)[:80]}")
    return {"total": len(results), "up": up, "down": len(results) - up, "results": results}


def _job_loadtest(params: dict[str, Any]) -> dict[str, Any]:
    """Fire N requests at a URL with C workers; report latency percentiles."""
    import concurrent.futures
    import time as _time

    import httpx

    url = params["url"]
    n, conc = params["requests"], params["concurrency"]
    log_progress(f"load test: {n} requests, {conc} concurrent → {url}")
    latencies: list[float] = []
    ok = 0
    codes: dict[int, int] = {}
    lock = threading.Lock()
    t_start = _time.time()

    def _one(_i: int) -> None:
        nonlocal ok
        with httpx.Client(timeout=20, verify=False, follow_redirects=True) as client:
            t0 = _time.time()
            try:
                resp = client.get(url)
                ms = (_time.time() - t0) * 1000
                with lock:
                    latencies.append(ms)
                    codes[resp.status_code] = codes.get(resp.status_code, 0) + 1
                    if resp.status_code < 400:
                        ok += 1
            except Exception:
                with lock:
                    codes[0] = codes.get(0, 0) + 1

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=conc) as pool:
        futures = [pool.submit(_one, i) for i in range(n)]
        for _ in concurrent.futures.as_completed(futures):
            _check_cancel()
            done += 1
            if done % max(1, n // 5) == 0:
                log_progress(f"  {done}/{n} done")
    elapsed = _time.time() - t_start

    def _pct(p: float) -> float:
        if not latencies:
            return 0.0
        s = sorted(latencies)
        return round(s[min(len(s) - 1, int(p / 100 * len(s)))], 1)

    return {
        "url": url, "requests": n, "concurrency": conc,
        "success": ok, "success_pct": round(100 * ok / n) if n else 0,
        "rps": round(n / elapsed, 1) if elapsed else 0,
        "p50": _pct(50), "p95": _pct(95), "p99": _pct(99),
        "min": round(min(latencies), 1) if latencies else 0,
        "max": round(max(latencies), 1) if latencies else 0,
        "mean": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "codes": codes,
    }


def _job_tls(params: dict[str, Any]) -> dict[str, Any]:
    """DNS + TLS certificate inspection: issuer, expiry, protocol, SANs."""
    import socket
    import ssl
    from datetime import datetime as _dt

    host, port = params["host"], params["port"]
    log_progress(f"resolving {host}…")
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
    except Exception as exc:
        raise RuntimeError(f"DNS resolution failed: {exc}")
    log_progress(f"{host} → {', '.join(ips)}")

    ctx = ssl.create_default_context()
    log_progress(f"TLS handshake with {host}:{port}…")
    with socket.create_connection((host, port), timeout=15) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
            proto = ssock.version()
            cipher = ssock.cipher()

    def _name(field: Any) -> str:
        return ", ".join("=".join(x) for rdn in (field or ()) for x in rdn)

    not_after = cert.get("notAfter")
    expiry = _dt.strptime(not_after, "%b %d %H:%M:%S %Y %Z") if not_after else None
    days_left = (expiry - _dt.utcnow()).days if expiry else None
    sans = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]

    status = "ok"
    if days_left is not None:
        if days_left < 0:
            status = "fail"
        elif days_left < 30:
            status = "warn"
    log_progress(f"cert valid {days_left} more day(s) · {proto}")

    return {
        "host": host, "port": port, "ips": ips,
        "issuer": _name(cert.get("issuer")), "subject": _name(cert.get("subject")),
        "expiry": not_after, "days_left": days_left,
        "protocol": proto, "cipher": cipher[0] if cipher else "",
        "sans": sans[:20], "status": status,
    }


_JOBS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "smoke": _job_smoke,
    "full": _job_full,
    "generate": _job_generate,
    "discover": _job_discover,
    "create": _job_create,
    "regression": _job_regression,
    "crawl_test": _job_crawl_test,
    "audit": _job_audit,
    "flaky": _job_flaky,
    "screenshot": _job_screenshot,
    "compare": _job_compare,
    "ping": _job_ping,
    "loadtest": _job_loadtest,
    "tls": _job_tls,
}
