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

import { Page } from '@playwright/test';
import { getTargetUrl, hasAuthCredentials, isMarketingSite } from './target';

export { getTargetUrl, hasAuthCredentials, isMarketingSite };

/** @deprecated Use hasAuthCredentials */
export function hasStagingCredentials(): boolean {
  return hasAuthCredentials();
}

/**
 * Authenticate against a Zyvor dashboard (not available on the public marketing site).
 */
export async function login(page: Page): Promise<void> {
  if (isMarketingSite()) {
    throw new Error(
      'Login is not available on zyvor.dev (marketing site). ' +
        'Set ENABLE_DASHBOARD_TESTS=true and a dashboard URL to run auth tests.'
    );
  }

  const targetUrl = getTargetUrl();
  const user = process.env.ZYVOR_TEST_USER;
  const password = process.env.ZYVOR_TEST_PASSWORD;

  if (!user || !password) {
    throw new Error(
      'Login requires ZYVOR_TEST_USER and ZYVOR_TEST_PASSWORD in .env'
    );
  }

  await page.goto(targetUrl);
  await page.getByLabel(/email|username/i).fill(user);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in|log in/i }).click();
  await page.waitForURL(/dashboard|home|vm/i, { timeout: 30000 });
}
