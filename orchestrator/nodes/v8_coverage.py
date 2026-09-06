# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Collect V8 JS coverage from Playwright test artifacts."""

from __future__ import annotations

from agents.coverage.v8_report import collect_v8_coverage
from orchestrator.state import PipelineState


def collect_v8_coverage_node(state: PipelineState) -> PipelineState:
    """Aggregate V8 coverage written during test execution.

    Runs in parallel with regression/api_validate/log_analyze, so it must
    return only the keys it changes rather than a full state spread — a
    spread would re-write `regression_diffs`/`api_validations`/`log_issues`
    with stale values and collide with those nodes' own writes in the same
    step.
    """
    summary = collect_v8_coverage()
    metadata = dict(state.get("metadata", {}))
    if summary:
        metadata["v8_coverage_percentage"] = summary.percentage
        metadata["v8_coverage_used_bytes"] = summary.used_bytes
        metadata["v8_coverage_total_bytes"] = summary.total_bytes
    return {"v8_coverage": summary, "metadata": metadata}
