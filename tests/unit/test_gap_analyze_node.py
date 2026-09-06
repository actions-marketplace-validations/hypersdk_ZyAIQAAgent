# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for orchestrator.nodes.gap_analyze."""

from __future__ import annotations

from agents.common.models import CoverageCandidate, CoverageGap
import orchestrator.nodes.gap_analyze as gap_analyze_module
from orchestrator.nodes.gap_analyze import gap_analyze


def test_short_circuits_on_existing_error():
    state = {"error": "boom"}
    assert gap_analyze(state) == state


def test_no_expansion_and_no_inventory_returns_empty_gaps(monkeypatch):
    result = gap_analyze({})
    assert result["coverage_gaps"] == []


def test_analyzes_gaps_when_inventory_present(monkeypatch):
    candidate = CoverageCandidate(id="c1", kind="route", path="/x", title="X")
    gap = CoverageGap(candidate=candidate)
    monkeypatch.setattr(gap_analyze_module, "analyze_gaps", lambda inventory: ([gap], [candidate]))

    result = gap_analyze({"coverage_inventory": [candidate]})
    assert result["coverage_gaps"] == [gap]
    assert result["metadata"]["coverage_gaps_remaining"] == 1
    assert result["metadata"]["coverage_covered_count"] == 1


def test_analyzes_gaps_when_expansion_enabled_even_without_inventory(monkeypatch):
    monkeypatch.setattr(gap_analyze_module, "analyze_gaps", lambda inventory: ([], []))
    result = gap_analyze({"expand_coverage": True})
    assert result["coverage_gaps"] == []
    assert result["metadata"]["coverage_gaps_remaining"] == 0
