// Copyright 2026 ZyvorAI Labs Private Limited
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { test, expect } from '../../playwright/fixtures/base';
import { waitForPageReady } from '../../playwright/utils/helpers';

test.describe('Zyvor Homepage', () => {
  test('homepage loads with hero content visible', { tag: ['@smoke'] }, async ({ page, consoleLogs }) => {
    await page.goto('/');
    await waitForPageReady(page);

    await expect.soft(page).toHaveTitle(/Zyvor|HyperSDK/i);
    await expect.soft(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
    const appErrors = consoleLogs.filter(
      (l) => l.startsWith('[error]') && !l.includes('Content Security Policy')
    );
    expect(appErrors).toHaveLength(0);
  });

  test('main navigation is accessible', { tag: ['@smoke', '@a11y'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    const nav = page.getByRole('navigation').first();
    await expect(nav).toBeVisible();
  });

  test('page has no critical accessibility landmarks', { tag: ['@a11y'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    await expect(page.locator('body')).toBeVisible();
    const links = page.getByRole('link');
    expect(await links.count()).toBeGreaterThan(0);
  });
});
