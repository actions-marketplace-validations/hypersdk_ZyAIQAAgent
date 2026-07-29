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
import { validateApiCalls } from '../../playwright/utils/api';

test.describe('Zyvor Product Suite', () => {
  test('product suite section is visible on homepage', { tag: ['@smoke'] }, async ({ page, apiCalls }) => {
    await page.goto('/');
    await waitForPageReady(page);

    await expect(
      page.getByRole('heading', { name: /14.*products|product suite|HyperSDK/i }).first()
    ).toBeVisible({ timeout: 15000 });

    const apiFailures = validateApiCalls(apiCalls, [
      { urlPattern: /zyvor\.dev/, method: 'GET', expectedStatus: 200 },
    ]);
    expect(apiFailures).toHaveLength(0);
  });

  test('key product names are present in page content', { tag: ['@smoke'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    const products = ['HyperSDK', 'hyper2kvm', 'Zeus OS', 'PacketWolf', 'Aether'];

    for (const product of products) {
      await expect.soft(page.getByText(product, { exact: false }).first()).toBeAttached();
    }
  });

  test('migration providers are mentioned in page content', { tag: ['@smoke'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    const providers = page.getByText(/VMware|OpenStack|KubeVirt/i);
    await expect(providers.first()).toBeAttached();
    expect(await providers.count()).toBeGreaterThan(0);
  });
});
