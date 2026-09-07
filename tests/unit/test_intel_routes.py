# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0

"""HTTP-level tests for /api/v2/intel/*. Skipped when FastAPI isn't installed
in the environment (the functions themselves are covered by the other
test_intel_* modules)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from orchestrator.dashboard import v2_routes
from orchestrator.persistence.store import MissionControlStore
from orchestrator.webhook import create_app


def _client(monkeypatch, tmp_path, store: MissionControlStore | None = None) -> TestClient:
    store = store or MissionControlStore(tmp_path / "state.db")
    monkeypatch.setattr(v2_routes, "get_store", lambda: store)
    monkeypatch.setattr("orchestrator.paths.repo_root", lambda: tmp_path)
    return TestClient(create_app())


def test_quarantine_api_round_trip(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    created = client.post("/api/v2/intel/quarantine", json={
        "title": "checkout pays",
        "file": "playwright/checkout.spec.ts",
        "reason": "price flake",
        "ttl_hours": 24,
    })
    assert created.status_code == 201
    key = created.json()["key"]

    listed = client.get("/api/v2/intel/quarantine")
    assert listed.status_code == 200
    assert listed.json()["quarantine"][0]["key"] == key

    released = client.delete(f"/api/v2/intel/quarantine/{key}")
    assert released.status_code == 200
    assert client.get("/api/v2/intel/quarantine").json()["quarantine"] == []


def test_quarantine_rejects_empty_title(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    resp = client.post("/api/v2/intel/quarantine", json={"title": "", "reason": "x"})
    assert resp.status_code == 400


def test_studio_404_for_unknown_job(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    assert client.get("/api/v2/intel/studio/missing").status_code == 404


def test_studio_for_finished_job(tmp_path, monkeypatch):
    store = MissionControlStore(tmp_path / "state.db")
    job = store.enqueue_job("smoke", {})
    store.claim_job()
    store.finish_job(job["id"], result={
        "cases": [{"title": "home", "status": "failed", "error": "expect(page).toHaveText('x')"}],
    })
    client = _client(monkeypatch, tmp_path, store)
    resp = client.get(f"/api/v2/intel/studio/{job['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["failed_count"] == 1
    assert body["primary"]["category"] == "assertion"


def test_select_and_health_endpoints_exist(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    health = client.get("/api/v2/intel/health")
    assert health.status_code == 200
    assert "counts" in health.json()
    selected = client.post("/api/v2/intel/select", json={"base": "HEAD~1", "head": "HEAD"})
    assert selected.status_code == 200
    assert "grep" in selected.json()
    assert "selected_files" in selected.json()


def test_select_tests_job_validates_without_url():
    from orchestrator.dashboard.jobs import VALID_KINDS, _validate

    assert "select_tests" in VALID_KINDS
    clean = _validate("select_tests", {"base": "main", "head": "HEAD"})
    assert clean["base"] == "main"
    assert clean["include_quarantined"] is False
