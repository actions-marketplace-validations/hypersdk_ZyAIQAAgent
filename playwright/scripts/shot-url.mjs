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

/**
 * On-demand screenshots of a URL at one or more viewports. Emits JSON to stdout.
 *
 * Usage: node shot-url.mjs <url> <outDir> [viewports] [full]
 *   viewports = comma list of desktop,tablet,mobile   (default: desktop)
 *   full = "full" for full-page capture
 *
 * Env: ZYVOR_IGNORE_HTTPS_ERRORS, ZYVOR_NO_SANDBOX,
 *      ZYVOR_TEST_USER/ZYVOR_TEST_PASSWORD (best-effort login).
 */

import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const url = process.argv[2];
const outDir = process.argv[3];
const viewports = (process.argv[4] || 'desktop').split(',').map((s) => s.trim());
const fullPage = process.argv[5] === 'full';

if (!url || !outDir) {
  console.error('Usage: node shot-url.mjs <url> <outDir> [viewports] [full]');
  process.exit(1);
}

const SIZES = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 820, height: 1180 },
  mobile: { width: 390, height: 844 },
};

function slug(text) {
  return (text || 'shot').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'shot';
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const context = await browser.newContext({
    ignoreHTTPSErrors: process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true',
  });
  const page = await context.newPage();

  const user = process.env.ZYVOR_TEST_USER, password = process.env.ZYVOR_TEST_PASSWORD;
  if (user && password) {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      const pass = page.locator('input[type="password"]').first();
      if ((await pass.count()) > 0) {
        await page.locator('input[type="email"], input[name*="user" i], input[name*="email" i], input[type="text"]').first().fill(user, { timeout: 5000 });
        await pass.fill(password, { timeout: 5000 });
        await Promise.all([
          page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {}),
          page.locator('button[type="submit"], input[type="submit"], button:has-text("sign in"), button:has-text("log in")').first().click({ timeout: 5000 }),
        ]);
      }
    } catch { /* skip */ }
  }

  fs.mkdirSync(outDir, { recursive: true });
  const base = slug(new URL(url).pathname);
  const shots = [];
  let status = 0;
  let title = '';
  for (const vp of viewports) {
    const size = SIZES[vp] || SIZES.desktop;
    await page.setViewportSize(size);
    const resp = await page.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => null);
    if (resp) status = resp.status();
    title = (await page.title().catch(() => '')) || '';
    const file = path.join(outDir, `${base}-${vp}.png`);
    await page.screenshot({ path: file, fullPage }).catch(() => {});
    shots.push({ viewport: vp, file: path.basename(file), width: size.width, height: size.height });
    console.error(`shot: ${vp} ${size.width}x${size.height}`);
  }
  await browser.close();
  process.stdout.write(JSON.stringify({ url, status, title: title.trim(), shots }));
}

run().catch((err) => { console.error(err); process.exit(1); });
