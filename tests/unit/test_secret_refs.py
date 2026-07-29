import pytest

from orchestrator.security.secrets import SecretReferenceError, assert_persistable, resolve_secret_refs


def test_raw_secret_rejected():
    with pytest.raises(SecretReferenceError):
        assert_persistable({"auth": {"token": "raw-token"}})


def test_env_secret_reference(monkeypatch):
    monkeypatch.setenv("QA_TOKEN", "secret-value")
    value = {"auth": {"token": {"$secret": "env:QA_TOKEN"}}}
    assert_persistable(value)
    assert resolve_secret_refs(value)["auth"]["token"] == "secret-value"
