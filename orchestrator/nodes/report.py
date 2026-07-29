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

"""Generate QA report."""

from __future__ import annotations

import os

from agents.reporter.agent import build_report
from orchestrator.state import PipelineState


def generate_report(state: PipelineState) -> PipelineState:
    """Build HTML and text report from test results."""
    if state.get("error") and not state.get("test_results"):
        return state

    test_results = state.get("test_results")
    if not test_results:
        return {**state, "error": state.get("error") or "No test results to report"}

    use_llm = os.environ.get("ENABLE_LLM_REPORT", "true").lower() == "true"
    report = build_report(
        test_results=test_results,
        source=state.get("source", "local"),
        failure_analysis=state.get("failure_analysis"),
        autofix_suggestions=state.get("autofix_suggestions"),
        v8_coverage=state.get("v8_coverage"),
        use_llm=use_llm,
    )

    try:
        from orchestrator.dashboard.history import append_run

        append_run(report, source=state.get("source", "local"))
    except Exception:
        pass

    return {
        **state,
        "report_path": report.html_path,
        "pdf_report_path": report.pdf_path,
        "report_summary": report.summary,
    }
