# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for orchestrator.nodes.execute."""

from __future__ import annotations

from agents.common.models import TestResult
import orchestrator.nodes.execute as execute_module
from orchestrator.nodes.execute import execute_tests


def test_runs_manual_tests_only_when_nothing_generated(monkeypatch, tmp_path):
    monkeypatch.setattr(execute_module, "_repo_root", lambda: tmp_path)
    calls = []
    result = TestResult(passed=1, failed=0, total=1)
    monkeypatch.setattr(
        execute_module, "run_playwright",
        lambda *, test_dirs, base_url: calls.append((test_dirs, base_url)) or result,
    )

    state = execute_tests({})
    assert state["test_results"] is result
    assert calls[0][0] == [str(tmp_path / "tests" / "manual")]


def test_includes_generated_test_dir_when_present(monkeypatch, tmp_path):
    monkeypatch.setattr(execute_module, "_repo_root", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(
        execute_module, "run_playwright",
        lambda *, test_dirs, base_url: calls.append(test_dirs) or TestResult(passed=1, failed=0, total=1),
    )

    execute_tests({"generated_tests": ["req-1.spec.ts"]})
    assert calls[0] == [str(tmp_path / "tests" / "manual"), str(tmp_path / "tests" / "generated")]


def test_uses_zyvor_base_url_env_var(monkeypatch, tmp_path):
    monkeypatch.setattr(execute_module, "_repo_root", lambda: tmp_path)
    monkeypatch.setenv("ZYVOR_BASE_URL", "https://staging.example.com")
    calls = []
    monkeypatch.setattr(
        execute_module, "run_playwright",
        lambda *, test_dirs, base_url: calls.append(base_url) or TestResult(passed=1, failed=0, total=1),
    )

    execute_tests({})
    assert calls == ["https://staging.example.com"]
