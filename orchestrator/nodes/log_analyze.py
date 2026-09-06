# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Browser log analysis node."""

from __future__ import annotations

from agents.logs.analyzer import analyze_test_results
from orchestrator.state import PipelineState


def log_analyze(state: PipelineState) -> PipelineState:
    """Analyze console and network logs from test results.

    Runs in parallel with regression/api_validate/v8_coverage (all read-only
    on `test_results`), so it must return only the key it changes rather than
    a full state spread — `merge_results` is the sole node that writes the
    aggregated fields back onto `test_results` after the fan-in.
    """
    test_results = state.get("test_results")
    if not test_results:
        return {}

    issues = analyze_test_results(test_results)
    return {"log_issues": issues}
