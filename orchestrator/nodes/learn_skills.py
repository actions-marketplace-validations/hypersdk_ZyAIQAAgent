# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Remember autofix patches that were applied and confirmed passing."""

from __future__ import annotations

import os

from agents.skills.store import load_skills, record_confirmed_fix, save_skills
from orchestrator.state import PipelineState


def learn_skills_node(state: PipelineState) -> PipelineState:
    """Persist applied autofix suggestions as skills once a retry passes."""
    metadata = state.get("metadata", {})
    test_results = state.get("test_results")

    if not metadata.get("autofix_patched_files"):
        return state
    if not test_results or not test_results.all_passed:
        return state

    run_id = os.environ.get("GITHUB_RUN_ID")
    skills = load_skills()
    for suggestion in state.get("autofix_suggestions", []):
        if "[applied to" not in suggestion.explanation:
            continue
        skills = record_confirmed_fix(skills, suggestion, run_id=run_id)
    save_skills(skills)

    return state
