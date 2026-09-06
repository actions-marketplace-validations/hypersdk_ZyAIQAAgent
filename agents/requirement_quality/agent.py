# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Requirement quality/gap-detection agent."""

from __future__ import annotations

import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agents.common.llm import LLMConfigError, content_to_text, get_llm, load_prompt
from agents.common.models import Requirement, RequirementQuality
from agents.requirement_quality.rule_fallback import evaluate_requirement_quality_rule_based


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1)
    return json.loads(text)


def _llm_available() -> bool:
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
    }
    if provider == "ollama":
        return True
    key = key_map.get(provider, "OPENAI_API_KEY")
    return bool(os.environ.get(key))


def evaluate_requirement_quality(req: Requirement) -> RequirementQuality:
    """Score a requirement for gaps/ambiguity — LLM when configured, rule-based
    fallback otherwise (mirrors agents/parser/agent.py's fallback shape)."""
    if not _llm_available():
        return evaluate_requirement_quality_rule_based(req)

    try:
        llm = get_llm()
        system = load_prompt("requirement_quality")
        payload = {
            "title": req.title,
            "description": req.description,
            "steps": [step.model_dump() for step in req.steps],
            "tags": req.tags,
        }
        response = llm.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=f"Evaluate this requirement:\n\n{json.dumps(payload, indent=2)}"),
            ]
        )
        raw = _extract_json(content_to_text(response.content))
        return RequirementQuality(
            requirement_id=req.id,
            score=float(raw["score"]),
            issues=[issue for issue in raw.get("issues", [])],
        )
    except (LLMConfigError, json.JSONDecodeError, ValueError, KeyError, Exception):
        return evaluate_requirement_quality_rule_based(req)
