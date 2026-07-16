/**
 * Route sweep — screenshot a list of routes at desktop/mobile. Emits JSON.
 * Modelled on zeus-os ui/scripts/visual-regression.mjs (animations off,
 * dynamic-content masking, no networkidle).
 *
 * Usage: node route-sweep.mjs <baseUrl> <outDir> <routes> <viewports>
 * Env: ZYVOR_IGNORE_HTTPS_ERRORS, ZYVOR_NO_SANDBOX, ZYVOR_TEST_USER/PASSWORD
 */

import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const base = (process.argv[2] || '').replace(/\/$/, '');
const outDir = process.argv[3];
const routes = (process.argv[4] || '/').split(',').map((s) => s.trim()).filter(Boolean);
const viewports = (process.argv[5] || 'desktop').split(',').map((s) => s.trim());

const SIZES = { desktop: { width: 1440, height: 900 }, mobile: { width: 375, height: 812 } };
const SETTLE_MS = Number(process.env.VISUAL_SETTLE_MS || '1500');
const emit = (m) => console.error(m);
function slug(r) { return (r === '/' ? 'home' : r.replace(/^\//, '').replace(/[^a-z0-9]+/gi, '-')).replace(/^-|-$/g, '') || 'home'; }

async function login(page) {
  const user = process.env.ZYVOR_TEST_USER, password = process.env.ZYVOR_TEST_PASSWORD;
  if (!user || !password) return;
  try {
    await page.goto(base + '/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    const pass = page.locator('input[type="password"]').first();
    if ((await pass.count()) > 0) {
      await page.locator('input[type="email"], input[name*="user" i], input[type="text"]').first().fill(user, { timeout: 5000 });
      await pass.fill(password, { timeout: 5000 });
      await Promise.all([
        page.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {}),
        page.locator('button[type="submit"], button:has-text("sign in"), button:has-text("log in")').first().click({ timeout: 5000 }),
      ]);
    }
  } catch { /* skip */ }
}

// dynamic content that flakes pixel diffs — mask it (zeus-os pattern)
async function dynamicMasks(page) {
  const sels = ['canvas', 'video', '[class*="recharts"]', 'time', '[class*="clock"]', '[class*="timestamp"]', '[class*="skeleton"]'];
  const masks = [];
  for (const sel of sels) {
    const loc = page.locator(sel);
    const n = await loc.count().catch(() => 0);
    for (let i = 0; i < Math.min(n, 20); i++) masks.push(loc.nth(i));
  }
  return masks;
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const context = await browser.newContext({ ignoreHTTPSErrors: process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true' });
  const page = await context.newPage();
  await login(page);

  fs.mkdirSync(outDir, { recursive: true });
  const shots = [];
  for (const route of routes) {
    for (const vp of viewports) {
      const size = SIZES[vp] || SIZES.desktop;
      await page.setViewportSize(size);
      const url = base + (route === '/' ? '/' : route);
      let status = 200;
      try {
        const resp = await page.goto(url, { waitUntil: 'load', timeout: 30000 });
        status = resp?.status() ?? 0;
        // wait for skeletons to disappear rather than networkidle (live apps never idle)
        await page.locator('[class*="skeleton"], .animate-pulse').first().waitFor({ state: 'hidden', timeout: 4000 }).catch(() => {});
        await page.waitForTimeout(SETTLE_MS);
      } catch (err) {
        emit(`route ${route} [${vp}] ERROR ${err}`);
      }
      const file = `${slug(route)}-${vp}.png`;
      const masks = await dynamicMasks(page);
      await page.screenshot({ path: path.join(outDir, file), fullPage: false, animations: 'disabled', mask: masks }).catch(() => {});
      shots.push({ route, viewport: vp, file, status });
      emit(`captured ${route} [${vp}] (HTTP ${status})`);
    }
  }
  await browser.close();
  process.stdout.write(JSON.stringify({ base, shots }));
}

run().catch((err) => { console.error(err); process.exit(1); });
