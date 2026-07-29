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
 * Core Web Vitals runner — measures LCP / CLS / INP(→TBT) / FCP / TTFB via
 * PerformanceObserver in the page (no web-vitals dep), grades vs Google
 * thresholds. Optional device profile + network throttle.
 *
 * Usage: node vitals.mjs <url> <outDir>
 * Env: ZYVOR_IGNORE_HTTPS_ERRORS, ZYVOR_NO_SANDBOX,
 *      ZYVOR_DEVICE (Playwright device name), ZYVOR_THROTTLE (3g|offline)
 * Progress → stderr, result JSON → stdout.
 */

import { chromium, devices } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const url = process.argv[2];
const outDir = process.argv[3];
if (!url) { console.error('Usage: node vitals.mjs <url> <outDir>'); process.exit(2); }
const emit = (m) => console.error(m);

// Google Core Web Vitals thresholds (good ≤ / poor >) in ms except CLS (unitless)
const THRESHOLDS = {
  LCP: [2500, 4000], INP: [200, 500], CLS: [0.1, 0.25], FCP: [1800, 3000], TTFB: [800, 1800],
};
function grade(metric, value) {
  if (value == null) return 'n/a';
  const [good, poor] = THRESHOLDS[metric];
  if (value <= good) return 'good';
  if (value <= poor) return 'needs-improvement';
  return 'poor';
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const deviceName = process.env.ZYVOR_DEVICE;
  const ctxOpts = { ignoreHTTPSErrors: process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true' };
  if (deviceName && devices[deviceName]) { Object.assign(ctxOpts, devices[deviceName]); emit(`vitals: device ${deviceName}`); }
  const context = await browser.newContext(ctxOpts);
  const page = await context.newPage();

  // network throttle via CDP
  const throttle = process.env.ZYVOR_THROTTLE;
  if (throttle === '3g' || throttle === 'offline') {
    try {
      const cdp = await context.newCDPSession(page);
      await cdp.send('Network.enable');
      await cdp.send('Network.emulateNetworkConditions', throttle === 'offline'
        ? { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 }
        : { offline: false, latency: 400, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8 });
      emit(`vitals: throttle ${throttle}`);
    } catch (e) { emit(`vitals: throttle failed — ${e}`); }
  }

  // install observers BEFORE navigation
  await page.addInitScript(() => {
    window.__vitals = { LCP: null, CLS: 0, FCP: null, INP: null };
    try {
      new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__vitals.LCP = e.startTime; })
        .observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__vitals.CLS += e.value; })
        .observe({ type: 'layout-shift', buffered: true });
      new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.name === 'first-contentful-paint') window.__vitals.FCP = e.startTime; })
        .observe({ type: 'paint', buffered: true });
      new PerformanceObserver((l) => { for (const e of l.getEntries()) { const d = e.duration; if (d > (window.__vitals.INP || 0)) window.__vitals.INP = d; } })
        .observe({ type: 'event', buffered: true, durationThreshold: 16 });
    } catch { /* older engines */ }
  });

  let status = 0, error = '';
  try {
    const resp = await page.goto(url, { waitUntil: 'load', timeout: 45000 });
    status = resp ? resp.status() : 0;
    // interact a bit to generate INP, and let LCP/CLS settle
    await page.mouse.move(200, 200).catch(() => {});
    await page.mouse.click(30, 30).catch(() => {});
    await page.keyboard.press('Tab').catch(() => {});
    await page.waitForTimeout(3500);
  } catch (e) { error = String(e.message || e).slice(0, 200); }

  // TTFB from Navigation Timing
  const nav = await page.evaluate(() => {
    const [n] = performance.getEntriesByType('navigation');
    const v = window.__vitals || {};
    return {
      LCP: v.LCP, CLS: v.CLS, FCP: v.FCP, INP: v.INP,
      TTFB: n ? n.responseStart : null,
      load: n ? n.loadEventEnd : null,
    };
  }).catch(() => ({}));

  let shot = '';
  if (outDir) {
    fs.mkdirSync(outDir, { recursive: true });
    try { await page.screenshot({ path: path.join(outDir, 'vitals.png') }); shot = 'vitals.png'; } catch { /* ignore */ }
  }
  await browser.close();

  const metrics = {};
  for (const m of ['LCP', 'INP', 'CLS', 'FCP', 'TTFB']) {
    const value = nav[m] == null ? null : (m === 'CLS' ? Math.round(nav[m] * 1000) / 1000 : Math.round(nav[m]));
    metrics[m] = { value, grade: grade(m, value) };
    emit(`vitals: ${m} = ${value == null ? 'n/a' : value} [${metrics[m].grade}]`);
  }
  const poor = Object.values(metrics).filter((x) => x.grade === 'poor').length;
  const overall = poor ? 'poor' : Object.values(metrics).some((x) => x.grade === 'needs-improvement') ? 'needs-improvement' : 'good';
  process.stdout.write(JSON.stringify({ url, status, error, device: deviceName || 'desktop', throttle: throttle || 'none', metrics, overall, shot }));
}

main().catch((e) => { console.error(e); process.exit(1); });
