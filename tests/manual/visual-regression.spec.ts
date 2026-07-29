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
import { screenshotOptions } from '../../playwright/utils/visual';
import { captureBaseline } from '../../playwright/utils/api';

test.describe('Visual Regression', () => {
  test('homepage visual baseline', { tag: ['@visual'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();

    const opts = await screenshotOptions(page);
    await expect(page).toHaveScreenshot('homepage-hero.png', {
      ...opts,
      maxDiffPixelRatio: 0.02,
    });

    // Optional: also feed the Pillow/Rust post-run pipeline when ENABLE_REGRESSION=true
    if (process.env.ENABLE_REGRESSION === 'true') {
      await captureBaseline(page, 'homepage-hero');
    }
  });

  test('products section visual baseline', { tag: ['@visual'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    const section = page.getByText(/14.*products|All 14|product suite/i).first();
    await section.scrollIntoViewIfNeeded();
    await expect(section).toBeAttached();

    const opts = await screenshotOptions(page);
    await expect(section).toHaveScreenshot('products-section.png', {
      ...opts,
      maxDiffPixelRatio: 0.02,
    });

    if (process.env.ENABLE_REGRESSION === 'true') {
      await captureBaseline(page, 'products-section');
    }
  });
});
