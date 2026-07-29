"""Unit tests for Playwright codegen → flow step import."""

from __future__ import annotations

import pytest

from agents.flow.codegen_import import import_codegen


SAMPLE = """
import { test, expect } from '@playwright/test';

test('example', async ({ page }) => {
  await page.goto('/vms');
  await page.getByRole('button', { name: 'Create VM' }).click();
  await page.getByLabel('name').fill('test-vm');
  await page.getByRole('button', { name: 'Submit' }).click();
  await expect(page.getByText('Running')).toBeVisible();
  await expect(page).toHaveURL('/vms/1');
});
"""


def test_import_basic_actions():
    steps = import_codegen(SAMPLE)
    actions = [s["action"] for s in steps]
    assert "goto" in actions
    assert "click" in actions
    assert "fill" in actions
    assert "assert" in actions or "assert_url" in actions
    goto = next(s for s in steps if s["action"] == "goto")
    assert goto["target"] == "/vms"
    fill = next(s for s in steps if s["action"] == "fill")
    assert fill["target"] == "name" and fill["value"] == "test-vm"


def test_empty_raises():
    with pytest.raises(ValueError):
        import_codegen("// nothing useful")
