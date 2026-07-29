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

"""Shared helpers for coverage expansion."""

from __future__ import annotations

import os

from orchestrator.state import PipelineState


def coverage_expansion_enabled(state: PipelineState) -> bool:
    """Return whether discovery/gap analysis should run."""
    if state.get("expand_coverage"):
        return True
    if state.get("metadata", {}).get("explicit_spec"):
        return False
    return os.environ.get("ENABLE_COVERAGE_EXPANSION", "false").lower() == "true"
