# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for orchestrator.nodes.autofix."""

from __future__ import annotations

from agents.common.models import AutofixSuggestion, TestResult
import orchestrator.nodes.autofix as autofix_module
from orchestrator.nodes.autofix import autofix_node


def test_disabled_by_default_is_a_noop(monkeypatch):
    monkeypatch.delenv("ENABLE_AUTOFIX", raising=False)
    state = {"test_results": TestResult(passed=0, failed=1, total=1)}
    assert autofix_node(state) == state


def test_no_test_results_is_a_noop(monkeypatch):
    monkeypatch.setenv("ENABLE_AUTOFIX", "true")
    state = {}
    assert autofix_node(state) == state


def test_all_passed_is_a_noop(monkeypatch):
    monkeypatch.setenv("ENABLE_AUTOFIX", "true")
    state = {"test_results": TestResult(passed=1, failed=0, total=1)}
    assert autofix_node(state) == state


def test_suggests_fixes_when_there_are_failures(monkeypatch):
    monkeypatch.setenv("ENABLE_AUTOFIX", "true")
    suggestion = AutofixSuggestion(test_title="t", original_selector=".old", suggested_selector=".new")
    monkeypatch.setattr(
        autofix_module, "suggest_fixes_from_results", lambda test_results, failure_analysis: [suggestion]
    )

    state = {"test_results": TestResult(passed=0, failed=1, total=1), "failure_analysis": "timeout"}
    result = autofix_node(state)
    assert result["autofix_suggestions"] == [suggestion]
