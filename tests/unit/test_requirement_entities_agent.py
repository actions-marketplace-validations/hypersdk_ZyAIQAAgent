# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the requirement data-model/flow extraction agent's
rule-based fallback (agents/requirement_entities/)."""

from __future__ import annotations

from agents.common.models import Requirement
from agents.requirement_entities.agent import extract_requirement_entities
from agents.requirement_entities.rule_fallback import extract_requirement_entities_rule_based


def test_finds_capitalized_domain_nouns_and_skips_stopwords():
    req = Requirement(
        id="req-1",
        title="Checkout applies a discount code to the Order",
        description="The Payment total should update after the discount is applied.",
    )
    result = extract_requirement_entities_rule_based(req)

    assert "Order" in result.data_models
    assert "Payment" in result.data_models
    assert "Checkout" in result.data_models
    # sentence-starters / boilerplate must not leak in as entities
    assert "The" not in result.data_models


def test_skips_all_caps_acronyms():
    req = Requirement(id="req-2", title="SSO login via API", description="Verify SSO works over HTTPS.")
    result = extract_requirement_entities_rule_based(req)

    assert "SSO" not in result.data_models
    assert "API" not in result.data_models
    assert "HTTPS" not in result.data_models


def test_purely_ui_requirement_yields_no_data_models():
    req = Requirement(id="req-3", title="the login page loads", description="verify the page renders.")
    result = extract_requirement_entities_rule_based(req)

    assert result.data_models == []


def test_flow_guessed_from_document_source_file_path():
    req = Requirement(
        id="req-4", title="Apply discount", description="...",
        source_type="document", origin_id="specs/checkout-flow.md",
    )
    result = extract_requirement_entities_rule_based(req)

    assert result.flows == ["Checkout Flow"]


def test_flow_empty_for_github_source_since_origin_id_is_not_a_path():
    req = Requirement(
        id="req-5", title="Apply discount", description="...",
        source_type="github", origin_id="42",
    )
    result = extract_requirement_entities_rule_based(req)

    assert result.flows == []


def test_extract_requirement_entities_falls_back_without_llm_key(monkeypatch):
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "AZURE_OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    req = Requirement(id="req-6", title="Checkout applies discount", description="...")
    result = extract_requirement_entities(req)

    assert result.requirement_id == "req-6"
    assert isinstance(result.data_models, list)
    assert isinstance(result.flows, list)
