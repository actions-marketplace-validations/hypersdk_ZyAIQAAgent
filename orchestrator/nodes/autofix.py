# Copyright 2026 ZyvorAI Labs Private Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Autofix node — suggest selector repairs after failure analysis."""

from __future__ import annotations

import os

from agents.autofix.agent import suggest_fixes_from_results
from orchestrator.state import PipelineState


def autofix_node(state: PipelineState) -> PipelineState:
    """Generate autofix suggestions when ENABLE_AUTOFIX=true."""
    if os.environ.get("ENABLE_AUTOFIX", "false").lower() != "true":
        return state

    test_results = state.get("test_results")
    if not test_results or test_results.all_passed:
        return state

    suggestions = suggest_fixes_from_results(
        test_results=test_results,
        failure_analysis=state.get("failure_analysis"),
    )
    return {**state, "autofix_suggestions": suggestions}
