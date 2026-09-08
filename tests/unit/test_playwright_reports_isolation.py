# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Regression guard for a real data-loss bug found live 2026-09-08.

Playwright's HTML reporter unconditionally clears its entire `outputFolder`
before writing a report -- even when zero tests run (e.g. a bad `testDir`
filter). `playwright/playwright.config.ts` used to point that folder
directly at `reports/`, the same directory Mission Control's live SQLite
state (`reports/mission-control.db`), job/run history, and artifacts live
in. Any `smoke`/`flow` job -- including the control test a
`chaos_inject`/`chaos_webhook` run drives -- invokes this config, so every
such run silently destroyed the live database mid-process, crashing the
durable-jobs worker thread the next time it touched a now-missing table.

Reproduced directly: a throwaway Playwright project with `outputFolder`
pointed at a directory containing an unrelated file wiped that file even
when the test run itself failed with "No tests found"; pointing
`outputFolder` at a scoped subdirectory instead left it untouched.

This is a static check, not a real Playwright invocation (that needs a
network fetch + ~180MB of browser binaries neither CI nor this sandbox
should require for what is fundamentally a one-line config regression
guard) -- it parses the real config file's reporter list."""

from __future__ import annotations

import re

from orchestrator.paths import repo_root

# Directories that MUST NOT be the entire value of any reporter's
# outputFolder/outputDir -- they hold live server state (mission-control.db)
# or other Playwright/report artifacts that must survive an unrelated run.
_FORBIDDEN_EXACT_OUTPUT_DIRS = {"reports"}


def _read_playwright_config() -> str:
    config_path = repo_root() / "playwright" / "playwright.config.ts"
    assert config_path.is_file(), f"expected {config_path} to exist"
    return config_path.read_text(encoding="utf-8")


def test_html_reporter_output_folder_is_not_the_bare_reports_root():
    config = _read_playwright_config()
    match = re.search(r"\['html',\s*\{([^}]*)\}\s*\]", config, re.DOTALL)
    assert match, "could not find the html reporter's config block in playwright.config.ts"
    block = match.group(1)

    output_folder_match = re.search(r"outputFolder:\s*path\.join\(([^)]*)\)", block)
    assert output_folder_match, f"could not find outputFolder in the html reporter block: {block!r}"
    join_args = [a.strip() for a in output_folder_match.group(1).split(",")]

    assert join_args[0] == "repoRoot", join_args
    assert len(join_args) > 2, (
        "html reporter's outputFolder is path.join(repoRoot, 'reports') with no further "
        "subdirectory -- this is exactly the bug that let Playwright's HTML reporter wipe "
        "the live mission-control.db on every smoke/flow run. Point it at a subdirectory, "
        "e.g. path.join(repoRoot, 'reports', 'playwright-report')."
    )
    stripped_args = [a.strip("'\"") for a in join_args[1:]]
    assert stripped_args[0] not in _FORBIDDEN_EXACT_OUTPUT_DIRS or len(stripped_args) > 1, stripped_args


def test_json_reporter_output_file_is_a_file_not_the_reports_root():
    """The json reporter writes a single named file (results.json), which
    is safe on its own -- confirms it hasn't regressed into something that
    could resolve to the bare reports/ directory itself."""
    config = _read_playwright_config()
    match = re.search(r"\['json',\s*\{([^}]*)\}\s*\]", config, re.DOTALL)
    assert match, "could not find the json reporter's config block in playwright.config.ts"
    output_file_match = re.search(r"outputFile:\s*path\.join\(([^)]*)\)", match.group(1))
    assert output_file_match, "could not find outputFile in the json reporter block"
    join_args = [a.strip().strip("'\"") for a in output_file_match.group(1).split(",")]
    assert join_args[-1].endswith(".json"), join_args
