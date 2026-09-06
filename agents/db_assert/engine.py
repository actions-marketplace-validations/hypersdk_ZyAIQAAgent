# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Loads runner_script.py's own source text, for handing to
orchestrator.security.sandbox.run_python() -- the sandbox takes code as a
string (mounted as a ConfigMap), not a file path, mirroring how
poc_generator.py's LLM-generated code is passed."""

from __future__ import annotations

from pathlib import Path


def load_runner_script() -> str:
    return (Path(__file__).resolve().parent / "runner_script.py").read_text(encoding="utf-8")
