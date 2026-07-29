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
