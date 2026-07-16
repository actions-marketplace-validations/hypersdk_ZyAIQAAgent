"""CLI entry point for Zyvor QA Agent."""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", message=".*OpenSSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph.*")

import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from orchestrator.graph import get_compiled_graph
from orchestrator.state import PipelineState

app = typer.Typer(
    name="zyvor-qa",
    help="Zyvor QA Agent — autonomous Playwright testing for Zyvor platform",
    no_args_is_help=True,
)


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")


def _initial_state(
    source: str = "local",
    spec: Optional[str] = None,
    pr_number: Optional[int] = None,
    expand_coverage: bool = False,
) -> PipelineState:
    spec_paths: list[str] = []
    if spec:
        if source == "github":
            from github.client import normalize_github_spec_path

            spec_paths = [normalize_github_spec_path(spec)]
        else:
            spec_paths = [str(Path(spec).resolve())]

    env_expand = os.environ.get("ENABLE_COVERAGE_EXPANSION", "false").lower() == "true"

    return {
        "source": source,
        "spec_paths": spec_paths,
        "spec_contents": [],
        "requirements": [],
        "generated_tests": [],
        "test_results": None,
        "failure_analysis": None,
        "report_path": None,
        "pdf_report_path": None,
        "report_summary": None,
        "pr_number": pr_number,
        "repo_full_name": os.environ.get("ZYVOR_PRODUCT_REPO"),
        "error": None,
        "metadata": {"explicit_spec": bool(spec)},
        "expand_coverage": expand_coverage or env_expand,
        "coverage_inventory": [],
        "coverage_gaps": [],
    }


def _run_discovery_subgraph(state: PipelineState) -> PipelineState:
    from orchestrator.nodes.discover import discover_coverage
    from orchestrator.nodes.fetch import fetch_requirements
    from orchestrator.nodes.gap_analyze import gap_analyze

    state = fetch_requirements(state)
    if state.get("error"):
        return state
    state = discover_coverage(state)
    return gap_analyze(state)


@app.command()
def run(
    source: str = typer.Option("local", help="Requirement source: local | github"),
    spec: Optional[str] = typer.Option(
        None,
        help="Spec path: local file, GitHub repo path (docs/specs/foo.md), or GitHub blob URL",
    ),
    pr_number: Optional[int] = typer.Option(None, help="PR number for GitHub comment"),
    expand_coverage: bool = typer.Option(
        False,
        "--expand-coverage",
        help="Discover routes/pages from GitHub code/docs and generate missing tests",
    ),
) -> None:
    """Run the full QA pipeline: fetch → parse → generate → execute → report → notify."""
    _load_env()
    graph = get_compiled_graph()
    state = _initial_state(
        source=source,
        spec=spec,
        pr_number=pr_number,
        expand_coverage=expand_coverage,
    )
    result = graph.invoke(state)

    if result.get("error"):
        typer.echo(f"Pipeline error: {result['error']}", err=True)
        if result.get("test_results"):
            tr = result["test_results"]
            typer.echo(
                f"Partial results: {tr.passed} passed, {tr.failed} failed",
                err=True,
            )
        raise typer.Exit(code=1)

    test_results = result.get("test_results")
    metadata = result.get("metadata", {})
    if metadata.get("coverage_inventory_size") is not None:
        typer.echo(
            f"Coverage: {metadata.get('coverage_inventory_size', 0)} candidates, "
            f"{metadata.get('coverage_gaps_remaining', 0)} gaps, "
            f"{metadata.get('coverage_tests_generated', 0)} new tests"
        )
    if test_results:
        typer.echo(
            f"Results: {test_results.passed} passed, "
            f"{test_results.failed} failed, {test_results.total} total"
        )
        generated = result.get("generated_tests", [])
        if generated:
            typer.echo(f"Generated tests: {len(generated)} file(s)")
    if result.get("report_path"):
        typer.echo(f"Report: {result['report_path']}")
    if result.get("pdf_report_path"):
        typer.echo(f"PDF report: {result['pdf_report_path']}")

    if test_results and test_results.failed > 0:
        raise typer.Exit(code=1)


@app.command()
def test() -> None:
    """Run Playwright tests only (skip parse/generate)."""
    _load_env()
    from agents.execution.runner import run_playwright

    base_url = os.environ.get("ZYVOR_BASE_URL", "https://zyvor.dev")
    repo_root = Path(__file__).resolve().parents[1]
    test_dirs = [str(repo_root / "tests" / "manual")]

    typer.echo(f"Running Playwright tests against {base_url}...")
    results = run_playwright(test_dirs=test_dirs, base_url=base_url)
    typer.echo(f"Results: {results.passed} passed, {results.failed} failed")

    if results.failed > 0:
        raise typer.Exit(code=1)


@app.command()
def generate(
    spec: Optional[str] = typer.Option(
        None,
        help="Spec path: local file, GitHub repo path (docs/specs/foo.md), or GitHub blob URL",
    ),
    source: str = typer.Option("local", help="Requirement source: local | github"),
    expand_coverage: bool = typer.Option(
        False,
        "--expand-coverage",
        help="Discover routes/pages from GitHub code/docs and generate missing tests",
    ),
) -> None:
    """Parse spec and generate Playwright tests (no execution)."""
    _load_env()

    subgraph_nodes = ["fetch", "discover", "gap_analyze", "parse", "generate"]
    state = _initial_state(source=source, spec=spec, expand_coverage=expand_coverage)

    for node in subgraph_nodes:
        if node == "fetch":
            from orchestrator.nodes.fetch import fetch_requirements

            state = fetch_requirements(state)
        elif node == "discover":
            from orchestrator.nodes.discover import discover_coverage

            state = discover_coverage(state)
        elif node == "gap_analyze":
            from orchestrator.nodes.gap_analyze import gap_analyze

            state = gap_analyze(state)
        elif node == "parse":
            from orchestrator.nodes.parse import parse_requirements

            state = parse_requirements(state)
        elif node == "generate":
            from orchestrator.nodes.generate import generate_tests

            state = generate_tests(state)

    if state.get("error"):
        typer.echo(f"Error: {state['error']}", err=True)
        raise typer.Exit(code=1)

    metadata = state.get("metadata", {})
    if metadata.get("coverage_inventory_size") is not None:
        typer.echo(
            f"Coverage: {metadata.get('coverage_inventory_size', 0)} candidates, "
            f"{metadata.get('coverage_gaps_remaining', 0)} gaps, "
            f"{metadata.get('coverage_tests_generated', 0)} new tests"
        )

    generated = state.get("generated_tests", [])
    typer.echo(f"Generated {len(generated)} test file(s):")
    for path in generated:
        typer.echo(f"  {path}")


@app.command()
def discover(
    source: str = typer.Option("github", help="Requirement source: local | github"),
    spec: Optional[str] = typer.Option(
        None,
        help="Optional spec path when fetching from GitHub",
    ),
    pr_number: Optional[int] = typer.Option(None, help="PR number for changed-file scoping"),
) -> None:
    """Discover coverage inventory and gaps without generating or running tests."""
    _load_env()
    state = _initial_state(
        source=source,
        spec=spec,
        pr_number=pr_number,
        expand_coverage=True,
    )
    state = _run_discovery_subgraph(state)

    if state.get("error"):
        typer.echo(f"Error: {state['error']}", err=True)
        raise typer.Exit(code=1)

    inventory = state.get("coverage_inventory", [])
    gaps = state.get("coverage_gaps", [])
    metadata = state.get("metadata", {})

    typer.echo(f"Discovered {len(inventory)} coverage candidate(s)")
    typer.echo(f"Uncovered gaps: {len(gaps)}")
    if metadata.get("discovered_paths"):
        typer.echo(f"Files scanned: {len(metadata['discovered_paths'])}")

    for gap in gaps[:20]:
        candidate = gap.candidate
        typer.echo(f"  [gap] {candidate.kind} {candidate.path} — {candidate.title}")
    if len(gaps) > 20:
        typer.echo(f"  ... and {len(gaps) - 20} more")


@app.command()
def create(
    description: str = typer.Argument(..., help="Natural language test description"),
    execute: bool = typer.Option(False, help="Run generated tests immediately"),
) -> None:
    """Create Playwright tests from natural language (Phase 4)."""
    _load_env()
    from agents.nl_create.agent import create_and_generate, create_from_natural_language
    from agents.parser.agent import save_requirements

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = repo_root / "tests" / "generated"

    typer.echo(f"Creating test from: {description}")
    try:
        parsed = create_from_natural_language(description)
    except Exception as exc:
        typer.echo(f"NL parsing failed: {exc}", err=True)
        raise typer.Exit(code=1)

    save_requirements(parsed, repo_root / "tests" / "fixtures" / "requirements.json")

    try:
        generated = create_and_generate(description, output_dir)
    except Exception as exc:
        typer.echo(f"Test generation failed: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Generated {len(generated)} test file(s):")
    for path in generated:
        typer.echo(f"  {path}")

    if execute:
        from agents.execution.runner import run_playwright

        results = run_playwright(test_dirs=[str(output_dir)])
        typer.echo(f"Results: {results.passed} passed, {results.failed} failed")
        if results.failed > 0:
            raise typer.Exit(code=1)


@app.command()
def regression(
    update_baselines: bool = typer.Option(False, help="Update screenshot baselines"),
) -> None:
    """Run visual regression check (Phase 2)."""
    _load_env()
    if update_baselines:
        os.environ["UPDATE_BASELINES"] = "true"
    os.environ["ENABLE_REGRESSION"] = "true"

    from orchestrator.nodes.regression import regression_check

    from agents.execution.runner import run_playwright

    base_url = os.environ.get("ZYVOR_BASE_URL", "https://zyvor.dev")
    repo_root = Path(__file__).resolve().parents[1]
    test_dirs = [str(repo_root / "tests" / "manual")]

    typer.echo("Running tests with screenshot capture...")
    test_results = run_playwright(test_dirs=test_dirs, base_url=base_url)

    state = regression_check({"test_results": test_results})
    diffs = state.get("regression_diffs", [])

    for d in diffs:
        status = "✓" if d.status == "pass" else "✗"
        typer.echo(f"  {status} {d.file}: {d.diff_percent}% — {d.message or d.status}")

    failed = [d for d in diffs if d.status == "fail"]
    if failed:
        raise typer.Exit(code=1)


@app.command()
def flow(
    url: str = typer.Argument(..., help="Base URL to run the journey against"),
    describe: Optional[str] = typer.Option(None, help="Journey in plain English"),
    steps: Optional[str] = typer.Option(None, help="Path to a file with one step per line"),
    video: bool = typer.Option(True, help="Record the journey as a video"),
    trace: bool = typer.Option(True, help="Capture a Playwright trace.zip (time-travel debugger)"),
    insecure: bool = typer.Option(False, help="Accept self-signed TLS"),
    username: Optional[str] = typer.Option(None, help="Login username (best-effort sign-in)"),
    password: Optional[str] = typer.Option(None, help="Login password"),
    session: Optional[str] = typer.Option(None, help="Reuse a saved session file (path or name under reports/artifacts/auth)"),
    browser: Optional[str] = typer.Option(None, help="Browser engine: chromium | firefox | webkit"),
    device: Optional[str] = typer.Option(None, help="Playwright device profile, e.g. 'iPhone 14'"),
    throttle: Optional[str] = typer.Option(None, help="Network throttle: 3g | offline"),
) -> None:
    """Drive a multi-step user journey and record it end-to-end as one video."""
    _load_env()
    import os as _os

    from agents.flow.engine import run_flow
    from agents.flow.parse import parse_flow

    if browser in ("chromium", "firefox", "webkit"):
        _os.environ["ZYVOR_BROWSER"] = browser
    if device:
        _os.environ["ZYVOR_DEVICE"] = device
    if throttle in ("3g", "offline"):
        _os.environ["ZYVOR_THROTTLE"] = throttle

    if steps:
        text, steps_mode = Path(steps).read_text(encoding="utf-8"), True
    elif describe:
        text, steps_mode = describe, False
    else:
        typer.echo("Provide --describe or --steps", err=True)
        raise typer.Exit(code=2)

    parsed, mode = parse_flow(text, steps_mode=steps_mode)
    typer.echo(f"{len(parsed)} step(s) parsed ({mode})")
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "reports" / "artifacts" / "flows" / "cli"
    session_path = ""
    if session:
        cand = Path(session)
        if not cand.exists():
            cand = repo_root / "reports" / "artifacts" / "auth" / session
        session_path = str(cand) if cand.exists() else ""
        if session_path:
            typer.echo(f"reusing session {session_path}")
    result = run_flow(
        url, parsed, out_dir, record=video, trace=trace, insecure=insecure,
        username=username or "", password=password or "", session=session_path,
        on_line=lambda line: typer.echo(line),
    )
    typer.echo(f"Result: {result['passed']}/{result['total']} steps passed")
    if result.get("video"):
        typer.echo(f"Journey video: {out_dir / result['video']}")
    if result.get("trace"):
        typer.echo(f"Trace (open at trace.playwright.dev): {out_dir / result['trace']}")
    if result["failed"] > 0:
        raise typer.Exit(code=1)


@app.command(name="route-sweep")
def route_sweep(
    url: str = typer.Argument(..., help="Base URL"),
    routes: str = typer.Option("/", help="Comma-separated routes to screenshot"),
    mobile: bool = typer.Option(False, help="Also capture mobile viewport"),
    update_baselines: bool = typer.Option(False, help="Capture/replace baselines"),
    auto: bool = typer.Option(False, help="Auto-discover routes by crawling the site"),
    max_pages: int = typer.Option(20, help="Max routes to discover when --auto"),
    insecure: bool = typer.Option(False, help="Accept self-signed TLS"),
) -> None:
    """Screenshot a list of routes and diff against baselines."""
    _load_env()
    from orchestrator.dashboard.jobs import _job_route_sweep

    vps = ["desktop"] + (["mobile"] if mobile else [])
    result = _job_route_sweep({
        "url": url,
        "routes": [r.strip() for r in routes.split(",") if r.strip()],
        "viewports": vps,
        "update_baselines": update_baselines,
        "insecure": insecure,
        "auto": auto,
        "max_pages": max_pages,
    })
    typer.echo(f"Swept {result['routes']} route(s): {result['fail_count']} changed, {result['new_baselines']} new baseline(s)")
    for row in result["sweep_rows"]:
        typer.echo(f"  {row['status']:8} {row['route']} [{row['viewport']}] {row['diff']}%")


@app.command(name="api-test")
def api_test(
    base: str = typer.Argument(..., help="API base URL"),
    spec: Optional[str] = typer.Option(None, help="OpenAPI spec URL or local JSON file"),
    workflow: Optional[str] = typer.Option(None, help="JSON file with an ordered workflow of steps"),
    include_writes: bool = typer.Option(False, help="Also exercise POST/PUT/PATCH/DELETE endpoints"),
    token: Optional[str] = typer.Option(None, help="Bearer token for auth"),
    api_key: Optional[str] = typer.Option(None, help="API key (sent as x-api-key)"),
    insecure: bool = typer.Option(False, help="Accept self-signed TLS"),
) -> None:
    """Validate REST endpoints against their OpenAPI schema, or run an API workflow."""
    _load_env()
    import json as _json

    from orchestrator.dashboard.jobs import _job_api_contract

    spec_val = None
    if spec:
        if spec.startswith(("http://", "https://")):
            spec_val = spec
        else:
            spec_val = _json.loads(Path(spec).read_text(encoding="utf-8"))
    wf = _json.loads(Path(workflow).read_text(encoding="utf-8")) if workflow else None
    auth = {}
    if token:
        auth["token"] = token
    if api_key:
        auth["apiKey"] = api_key

    result = _job_api_contract({
        "url": base,
        "mode": "workflow" if wf else "spec",
        "spec": spec_val,
        "workflow": wf,
        "auth": auth or None,
        "include_writes": include_writes,
        "insecure": insecure,
        "max_endpoints": 200,
        "path_params": None,
    })
    typer.echo(f"API contract ({result['mode']}): {result['passed']}/{result['total']} passed")
    rows = result.get("endpoints") if result["mode"] == "spec" else result.get("steps")
    for r in rows or []:
        mark = "✓" if r.get("ok") else "✗"
        label = f"{r.get('method')} {r.get('path')}" if result["mode"] == "spec" else r.get("desc")
        detail = " | ".join(r.get("schema_errors") or []) or r.get("error") or r.get("note") or ""
        typer.echo(f"  {mark} {label} → {r.get('status')} {detail}")
    if result["failed"] > 0:
        raise typer.Exit(code=1)


@app.command(name="auth-test")
def auth_test(
    base: str = typer.Argument(..., help="App base URL"),
    login_url: Optional[str] = typer.Option(None, help="Login page path to drive in-browser"),
    api_login: Optional[str] = typer.Option(None, help="API login endpoint to POST credentials to"),
    protected: str = typer.Option("/", help="A protected path that requires auth"),
    logout_url: Optional[str] = typer.Option(None, help="Logout endpoint (to test session clearing)"),
    username: Optional[str] = typer.Option(None, help="Login username"),
    password: Optional[str] = typer.Option(None, help="Login password"),
    save_session: bool = typer.Option(True, help="Save the session for reuse by flow/realtime"),
    insecure: bool = typer.Option(False, help="Accept self-signed TLS"),
) -> None:
    """Log in, capture a reusable session, and assert auth/session behaviour."""
    _load_env()
    from orchestrator.dashboard.jobs import _job_auth_test

    result = _job_auth_test({
        "url": base, "login_url": login_url or "", "api_login": api_login or "",
        "protected": protected, "logout_url": logout_url or "",
        "username": username or "", "password": password or "",
        "save_session": save_session, "insecure": insecure,
    })
    typer.echo(f"Auth & session: {result['passed']}/{result['total']} checks passed")
    for c in result.get("checks") or []:
        typer.echo(f"  {'✓' if c['ok'] else '✗'} {c['name']} — {c.get('detail', '')}")
    if result.get("session_name"):
        typer.echo(f"Session saved as: {result['session_name']} (reuse with flow/realtime --session)")
    if result["failed"] > 0:
        raise typer.Exit(code=1)


@app.command()
def realtime(
    url: str = typer.Argument(..., help="App base URL"),
    ws: Optional[str] = typer.Option(None, help="WebSocket path or full ws(s):// URL"),
    sse: Optional[str] = typer.Option(None, help="SSE endpoint path"),
    ticket_url: Optional[str] = typer.Option(None, help="One-time WS-ticket issue endpoint"),
    token: Optional[str] = typer.Option(None, help="Auth token (Bearer/subprotocol/query)"),
    subprotocol_jwt: bool = typer.Option(False, help="Send token via Sec-WebSocket-Protocol: access_token,<jwt>"),
    expect_messages: int = typer.Option(1, help="Minimum messages expected in the window"),
    window_ms: int = typer.Option(15000, help="Observation window (ms)"),
    live_selector: Optional[str] = typer.Option(None, help="CSS selector of a live region to watch for updates"),
    session: Optional[str] = typer.Option(None, help="Reuse a saved session (name under reports/artifacts/auth)"),
    insecure: bool = typer.Option(False, help="Accept self-signed TLS"),
) -> None:
    """Assert WebSocket/SSE streams are live and dashboard live regions update."""
    _load_env()
    from orchestrator.dashboard.jobs import _job_realtime

    result = _job_realtime({
        "url": url, "ws": ws or "", "sse": sse or "", "ticket_url": ticket_url or "",
        "ticket_query": "ticket", "token": token or "", "subprotocol_jwt": subprotocol_jwt,
        "expect_messages": expect_messages, "window_ms": window_ms,
        "live_selector": live_selector or "", "session": session or "", "insecure": insecure,
    })
    typer.echo(f"Live data: {result['passed']}/{result['total']} checks passed")
    for c in result.get("checks") or []:
        typer.echo(f"  {'✓' if c['ok'] else '✗'} {c['name']} — {c.get('detail', '')}")
    if result["failed"] > 0:
        raise typer.Exit(code=1)


@app.command()
def vitals(
    url: str = typer.Argument(..., help="URL to measure"),
    device: Optional[str] = typer.Option(None, help="Playwright device profile, e.g. 'iPhone 14'"),
    throttle: Optional[str] = typer.Option(None, help="Network throttle: 3g | offline"),
    insecure: bool = typer.Option(False, help="Accept self-signed TLS"),
) -> None:
    """Measure Core Web Vitals (LCP/CLS/INP/FCP/TTFB) and grade them."""
    _load_env()
    from orchestrator.dashboard.jobs import _job_vitals

    result = _job_vitals({"url": url, "device": device or "", "throttle": throttle or "", "insecure": insecure})
    typer.echo(f"Overall: {result.get('overall', '?').upper()}")
    for name, m in (result.get("metrics") or {}).items():
        typer.echo(f"  {name:5} {str(m.get('value')):>8}  [{m.get('grade')}]")


@app.command()
def serve(
    port: int = typer.Option(8080, help="Webhook server port"),
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    tls: bool = typer.Option(False, help="Serve over HTTPS (generates a self-signed cert if none given)"),
    tls_cert: Optional[str] = typer.Option(None, help="Path to a TLS certificate (PEM)"),
    tls_key: Optional[str] = typer.Option(None, help="Path to the TLS private key (PEM)"),
) -> None:
    """Start FastAPI webhook server for GitHub events + Mission Control dashboard."""
    _load_env()
    import uvicorn

    from orchestrator.webhook import create_app

    ssl_kwargs: dict[str, str] = {}
    if tls or tls_cert or tls_key:
        cert, key = _ensure_tls_cert(tls_cert, tls_key, host)
        ssl_kwargs = {"ssl_certfile": cert, "ssl_keyfile": key}
        typer.echo(f"Starting HTTPS server on {host}:{port} (cert: {cert})")
    else:
        typer.echo(f"Starting webhook server on {host}:{port}")
    uvicorn.run(create_app(), host=host, port=port, **ssl_kwargs)


def _ensure_tls_cert(cert: Optional[str], key: Optional[str], host: str) -> tuple[str, str]:
    """Return (cert_path, key_path); generate a self-signed pair if not provided."""
    import subprocess

    if cert and key:
        return cert, key
    cert_dir = Path.home() / ".zyvor-qa" / "tls"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = cert_dir / "server.crt", cert_dir / "server.key"
    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)
    cn = host if host not in ("0.0.0.0", "") else "localhost"
    typer.echo(f"Generating self-signed TLS certificate (CN={cn}) → {cert_dir}")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key_path), "-out", str(cert_path),
            "-days", "825", "-subj", f"/CN={cn}",
            "-addext", f"subjectAltName=DNS:{cn},DNS:localhost,IP:127.0.0.1",
        ],
        check=True, capture_output=True,
    )
    return str(cert_path), str(key_path)


if __name__ == "__main__":
    app()


def main() -> None:
    app()
