from orchestrator.persistence.store import MissionControlStore


def test_job_lifecycle(tmp_path):
    store = MissionControlStore(tmp_path / "state.db")
    job = store.enqueue_job("smoke", {"url": "https://zyvor.dev"}, requested_by="tester")
    assert job["status"] == "queued"
    claimed = store.claim_job()
    assert claimed and claimed["id"] == job["id"]
    assert claimed["status"] == "running"
    store.finish_job(job["id"], result={"passed": 4})
    complete = store.get_job(job["id"])
    assert complete and complete["status"] == "succeeded"
    assert complete["result"]["passed"] == 4


def test_idempotency(tmp_path):
    store = MissionControlStore(tmp_path / "state.db")
    first = store.enqueue_job("smoke", {}, idempotency_key="deploy-123")
    second = store.enqueue_job("smoke", {}, idempotency_key="deploy-123")
    assert first["id"] == second["id"]


def test_schedule_persists_and_redacts(tmp_path):
    store = MissionControlStore(tmp_path / "state.db")
    schedule = store.add_schedule(
        "realtime",
        {"token": {"$secret": "env:QA_TOKEN"}, "url": "https://zyvor.dev"},
        60,
    )
    assert schedule["params"]["token"] == "***"
    assert MissionControlStore(tmp_path / "state.db").list_schedules()[0]["id"] == schedule["id"]


def test_findings_are_deduplicated(tmp_path):
    store = MissionControlStore(tmp_path / "state.db")
    first = store.add_finding("audit", "high", "Broken API", fingerprint="api:/v1/x")
    second = store.add_finding("audit", "high", "Broken API", fingerprint="api:/v1/x")
    assert first == second
    rows = store.list_findings()["findings"]
    assert rows[0]["occurrences"] == 2


def test_webhook_delivery_deduplication(tmp_path):
    store = MissionControlStore(tmp_path / "state.db")
    assert store.record_webhook_delivery("d1", "push", "abc")
    assert not store.record_webhook_delivery("d1", "push", "abc")


def test_persisted_job_rejects_raw_token(tmp_path):
    import pytest
    from orchestrator.security.secrets import SecretReferenceError

    store = MissionControlStore(tmp_path / "state.db")
    with pytest.raises(SecretReferenceError):
        store.enqueue_job("realtime", {"token": "raw-secret"})
