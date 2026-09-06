# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from agents.common.models import ApiValidationResult, LogIssue, RegressionDiff, TestResult
from orchestrator.nodes.merge_results import merge_results


def test_merge_results_copies_parallel_outputs_onto_test_results():
    test_results = TestResult(passed=1, failed=0, total=1, cases=[])
    regression_diffs = [RegressionDiff(file="a.png", status="fail")]
    api_validations = [ApiValidationResult(url="/x", passed=False)]
    log_issues = [LogIssue(test_title="t", severity="error", source="console", message="boom")]

    result = merge_results(
        {
            "test_results": test_results,
            "regression_diffs": regression_diffs,
            "api_validations": api_validations,
            "log_issues": log_issues,
        }
    )

    merged = result["test_results"]
    assert merged is test_results
    assert merged.regression_diffs == regression_diffs
    assert merged.api_validations == api_validations
    assert merged.log_issues == log_issues


def test_merge_results_noop_without_test_results():
    assert merge_results({}) == {}
