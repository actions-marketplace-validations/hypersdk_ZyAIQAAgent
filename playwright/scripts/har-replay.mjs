/**
 * HAR record / replay — capture network as HAR, then drive the page against it.
 *
 * Usage: node har-replay.mjs <cfgJsonFile> <outDir>
 * cfg: { base, mode: 'record'|'replay', har, routes?: string[], expect_text?, insecure?,
 *        not_found_ok?: bool }
 *
 * Progress → stderr. Result JSON → stdout.
 */

import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const cfgFile = process.argv[2];
const outDir = process.argv[3];
if (!cfgFile || !outDir) {
  console.error('Usage: node har-replay.mjs <cfgJsonFile> <outDir>');
  process.exit(2);
}
const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf-8'));
const base = (cfg.base || '').replace(/\/$/, '');
const mode = (cfg.mode || 'replay').toLowerCase();
const routes = (cfg.routes && cfg.routes.length) ? cfg.routes : ['/'];
const emit = (m) => console.error(m);

fs.mkdirSync(outDir, { recursive: true });
const harPath = cfg.har || path.join(outDir, 'capture.har');

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const checks = [];
  let passed = 0;
  let failed = 0;

  if (mode === 'record') {
    emit(`har: recording ${routes.length} route(s) → ${harPath}`);
    const context = await browser.newContext({
      ignoreHTTPSErrors: cfg.insecure || process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true',
      recordHar: { path: harPath, mode: 'full', content: 'embed' },
    });
    const page = await context.newPage();
    for (const route of routes) {
      const url = /^https?:/.test(route) ? route : base + (route.startsWith('/') ? route : '/' + route);
      const name = `record ${route}`;
      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForTimeout(800);
        checks.push({ name, ok: true, detail: url });
        passed++;
        emit(`✓ ${name}`);
      } catch (err) {
        checks.push({ name, ok: false, detail: String(err.message || err).slice(0, 200) });
        failed++;
        emit(`✗ ${name}`);
      }
    }
    await context.close(); // flushes HAR
    await browser.close();
    if (!fs.existsSync(harPath)) {
      failed++;
      checks.push({ name: 'har file written', ok: false, detail: 'missing after record' });
    } else {
      checks.push({ name: 'har file written', ok: true, detail: harPath });
      passed++;
    }
  } else {
    if (!fs.existsSync(harPath)) {
      await browser.close();
      process.stdout.write(JSON.stringify({
        mode, base, har: harPath, passed: 0, failed: 1, total: 1,
        checks: [{ name: 'har exists', ok: false, detail: harPath }],
      }));
      return;
    }
    emit(`har: replaying from ${harPath}`);
    const context = await browser.newContext({
      ignoreHTTPSErrors: cfg.insecure || process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true',
    });
    // Serve from HAR; update:false fails missing routes unless notFound is continue
    await context.routeFromHAR(harPath, {
      update: false,
      notFound: cfg.not_found_ok ? 'fallback' : 'abort',
    });
    const page = await context.newPage();
    const route = routes[0];
    const url = /^https?:/.test(route) ? route : base + (route.startsWith('/') ? route : '/' + route);
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      checks.push({ name: 'page loads from HAR', ok: true, detail: url });
      passed++;
      emit('✓ page loads from HAR');
    } catch (err) {
      checks.push({ name: 'page loads from HAR', ok: false, detail: String(err.message || err).slice(0, 200) });
      failed++;
      emit('✗ page loads from HAR');
    }
    if (cfg.expect_text) {
      try {
        await page.getByText(cfg.expect_text, { exact: false }).first().waitFor({ state: 'visible', timeout: 10000 });
        checks.push({ name: `text "${cfg.expect_text}"`, ok: true, detail: '' });
        passed++;
      } catch (err) {
        checks.push({ name: `text "${cfg.expect_text}"`, ok: false, detail: String(err.message || err).slice(0, 120) });
        failed++;
      }
    }
    let shot = '';
    try {
      shot = 'replay.png';
      await page.screenshot({ path: path.join(outDir, shot) });
    } catch { /* ignore */ }
    await context.close();
    await browser.close();
    process.stdout.write(JSON.stringify({
      mode, base, har: harPath, passed, failed, total: passed + failed, checks, shot,
    }));
    return;
  }

  process.stdout.write(JSON.stringify({
    mode, base, har: harPath, passed, failed, total: passed + failed, checks,
  }));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
