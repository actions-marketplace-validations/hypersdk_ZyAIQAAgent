# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0

from orchestrator.intelligence.classify import classify_error, classify_history


def test_classify_error_selector():
    assert classify_error("Timeout exceeded while waiting for locator('button.submit')") == "selector"


def test_classify_error_assertion():
    assert classify_error("Error: expect(received).toHaveText('Welcome')") == "assertion"


def test_classify_error_infra():
    assert classify_error("net::ERR_CONNECTION_REFUSED at https://x.io") == "infra"


def test_classify_error_data():
    assert classify_error("UNIQUE constraint failed: users.email") == "data"


def test_classify_error_empty_is_unknown():
    assert classify_error("") == "unknown"


def test_history_all_pass_is_healthy():
    result = classify_history(["passed", "passed", "passed"])
    assert result["verdict"] == "healthy"
    assert result["recommend_quarantine"] is False


def test_history_all_fail_is_failing():
    result = classify_history(["failed", "failed"], last_error="expect(page).toHaveText('x')")
    assert result["verdict"] == "failing"
    assert result["category"] == "assertion"


def test_history_mix_is_flaky_and_recommends_quarantine():
    result = classify_history(["passed", "failed", "passed", "failed"])
    assert result["verdict"] == "flaky"
    assert result["recommend_quarantine"] is True
    assert result["fail_pct"] == 50


def test_history_two_runs_does_not_quarantine_yet():
    result = classify_history(["passed", "failed"])
    assert result["verdict"] == "flaky"
    assert result["recommend_quarantine"] is False
