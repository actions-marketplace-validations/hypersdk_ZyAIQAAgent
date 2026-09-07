# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0

from orchestrator.intelligence.quarantine import add
from orchestrator.intelligence.select import select_tests


def test_changed_spec_is_selected():
    result = select_tests(["playwright/login.spec.ts", "README.md"])
    assert "playwright/login.spec.ts" in result["selected_files"]
    assert result["reasons"]["playwright/login.spec.ts"] == "changed-test-file"
    assert result["run_recommended"] is True
    assert "login" in result["grep"]


def test_product_change_without_tests_falls_back_to_smoke():
    result = select_tests(["src/checkout.ts"])
    assert result["fallback"] == "@smoke"
    assert result["run_recommended"] is True


def test_infra_only_change_does_not_recommend_product_run():
    result = select_tests(["docs/tutorials/01-getting-started.md", "orchestrator/cli.py"])
    assert result["infra_only"] is True
    assert result["run_recommended"] is False


def test_requirement_links_are_included():
    result = select_tests(
        ["docs/spec.md"],
        linked_tests=["playwright/generated/order.spec.ts"],
    )
    assert "playwright/generated/order.spec.ts" in result["selected_files"]
    assert result["reasons"]["playwright/generated/order.spec.ts"] == "requirement-link"


def test_select_tests_job_validates_without_url():
    from orchestrator.dashboard.jobs import VALID_KINDS, _JOBS, _validate

    assert "select_tests" in VALID_KINDS
    assert "select_tests" in _JOBS
    clean = _validate("select_tests", {"base": "main", "head": "HEAD"})
    assert clean["base"] == "main"
    assert clean["include_quarantined"] is False


def test_quarantined_file_is_dropped(tmp_path):
    add("login should work", file="playwright/login.spec.ts", reason="flake", root=tmp_path)
    result = select_tests(["playwright/login.spec.ts"], root=tmp_path)
    assert result["selected_files"] == []
    assert result["dropped_quarantine"]
    kept = select_tests(["playwright/login.spec.ts"], root=tmp_path, include_quarantined=True)
    assert "playwright/login.spec.ts" in kept["selected_files"]
