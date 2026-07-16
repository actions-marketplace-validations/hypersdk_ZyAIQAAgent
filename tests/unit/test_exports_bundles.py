"""Unit tests for report-bundle builders (agents/reporter/exports.py)."""

from __future__ import annotations

import os

import pytest

from agents.reporter import exports


@pytest.fixture(autouse=True)
def _no_pdf(monkeypatch):
    # keep tests fast + headless-safe: skip the PDF renderer
    monkeypatch.setenv("ENABLE_PDF_REPORT", "false")


def test_build_flow_bundle_writes_html_and_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "_repo_root", lambda: tmp_path)
    (tmp_path / "templates").mkdir()
    # reuse the real templates dir for rendering
    real_templates = os.path.join(os.path.dirname(exports.__file__), "..", "..", "templates")
    for name in ("flow-report.html.j2",):
        src = os.path.join(real_templates, name)
        with open(src) as fh:
            (tmp_path / "templates" / name).write_text(fh.read())
    steps = [
        {"n": 1, "action": "goto", "desc": "go to /", "status": "passed", "error": ""},
        {"n": 2, "action": "assert", "desc": 'assert "Hi"', "status": "failed", "error": "not found"},
    ]
    hrefs = exports.build_flow_bundle("https://x.io", steps, {"passed": 1, "failed": 1, "total": 2, "video": None})
    assert "html" in hrefs and "csv" in hrefs
    job_dirs = list((tmp_path / "reports" / "jobs").iterdir())
    assert job_dirs, "a job dir should be created"
    csv = (job_dirs[0] / "report.csv").read_text()
    assert "go to /" in csv and "assert" in csv


def test_build_route_sweep_bundle_writes_html_and_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "_repo_root", lambda: tmp_path)
    (tmp_path / "templates").mkdir()
    real_templates = os.path.join(os.path.dirname(exports.__file__), "..", "..", "templates")
    with open(os.path.join(real_templates, "route-sweep-report.html.j2")) as fh:
        (tmp_path / "templates" / "route-sweep-report.html.j2").write_text(fh.read())
    rows = [
        {"route": "/", "viewport": "desktop", "status": "ok", "diff": 0.0, "cur": "/reports/x/home.png"},
        {"route": "/a", "viewport": "mobile", "status": "fail", "diff": 4.2, "cur": "/reports/x/a.png"},
    ]
    hrefs = exports.build_route_sweep_bundle("https://x.io", rows, {"fail_count": 1, "new_baselines": 0, "routes": 2})
    assert "html" in hrefs and "csv" in hrefs
    job_dirs = list((tmp_path / "reports" / "jobs").iterdir())
    csv = (job_dirs[0] / "report.csv").read_text()
    assert "/a" in csv and "fail" in csv
    html = (job_dirs[0] / "report.html").read_text()
    assert "Route sweep" in html and "4.2" in html


def _copy_template(tmp_path, name):
    real = os.path.join(os.path.dirname(exports.__file__), "..", "..", "templates", name)
    with open(real) as fh:
        (tmp_path / "templates" / name).write_text(fh.read())


def test_build_api_contract_bundle_spec_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "_repo_root", lambda: tmp_path)
    (tmp_path / "templates").mkdir()
    _copy_template(tmp_path, "api-contract-report.html.j2")
    rows = [
        {"method": "GET", "path": "/posts/1", "status": 200, "ok": True, "schema_errors": [], "note": "", "latency_ms": 40},
        {"method": "GET", "path": "/users/1", "status": 200, "ok": False, "schema_errors": ["$.email: required missing"], "note": "", "latency_ms": 30},
    ]
    hrefs = exports.build_api_contract_bundle("https://api.x.io", "spec", rows, {"passed": 1, "failed": 1, "total": 2})
    assert "html" in hrefs and "csv" in hrefs
    job = next((tmp_path / "reports" / "jobs").iterdir())
    assert "required missing" in (job / "report.csv").read_text()
    assert "/users/1" in (job / "report.html").read_text()


def test_build_vitals_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "_repo_root", lambda: tmp_path)
    (tmp_path / "templates").mkdir()
    _copy_template(tmp_path, "vitals-report.html.j2")
    data = {"device": "desktop", "throttle": "none", "overall": "good",
            "metrics": {"LCP": {"value": 1444, "grade": "good"}, "CLS": {"value": 0.02, "grade": "good"}}}
    hrefs = exports.build_vitals_bundle("https://x.io", data)
    assert "html" in hrefs and "csv" in hrefs
    job = next((tmp_path / "reports" / "jobs").iterdir())
    assert "LCP" in (job / "report.csv").read_text()
    assert "Core Web Vitals" in (job / "report.html").read_text()
