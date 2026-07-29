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

"""Apply autofix patches and optionally re-run tests."""

from __future__ import annotations

import os

from agents.autofix.apply import apply_autofix_patches
from orchestrator.state import PipelineState


def apply_autofix_node(state: PipelineState) -> PipelineState:
    """Patch test files from autofix suggestions when ENABLE_AUTOFIX_APPLY=true."""
    if os.environ.get("ENABLE_AUTOFIX_APPLY", "false").lower() != "true":
        return state

    suggestions = state.get("autofix_suggestions", [])
    if not suggestions:
        return state

    updated, patched_files = apply_autofix_patches(suggestions)
    metadata = dict(state.get("metadata", {}))
    metadata["autofix_patches_applied"] = len(patched_files)
    metadata["autofix_patched_files"] = patched_files
    if patched_files:
        metadata["autofix_retries"] = metadata.get("autofix_retries", 0) + 1

    return {
        **state,
        "autofix_suggestions": updated,
        "metadata": metadata,
    }
