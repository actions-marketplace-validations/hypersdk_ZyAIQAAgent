/**
 * E2E flow runner — drive a multi-step user journey and record it as one video.
 * Modelled on zeus-os ui/scripts/e2e-create-vm-wizard.mjs.
 *
 * Usage: node flow-run.mjs <flowJsonFile> <outDir>
 *   flow JSON: { base, steps: [{action,target,value,assertion}], record: bool }
 *
 * Env: ZYVOR_IGNORE_HTTPS_ERRORS, ZYVOR_NO_SANDBOX,
 *      ZYVOR_TEST_USER / ZYVOR_TEST_PASSWORD (best-effort login).
 * Progress → stderr (live panel). Result JSON → stdout.
 */

import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const flowFile = process.argv[2];
const outDir = process.argv[3];
if (!flowFile || !outDir) {
  console.error('Usage: node flow-run.mjs <flowJsonFile> <outDir>');
  process.exit(2);
}
const flow = JSON.parse(fs.readFileSync(flowFile, 'utf-8'));
const base = (flow.base || '').replace(/\/$/, '');
const steps = flow.steps || [];
const record = flow.record !== false;

const FAIL_SNIPPETS = ['Something went wrong', 'ReferenceError', 'TypeError', 'is not defined', 'Application error', 'Cannot read propert'];
const emit = (m) => console.error(m);
function slug(t) { return (t || 'step').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'step'; }

// navigate with a few retries — survives server churn / cold starts (zeus-os pattern)
async function gotoRetry(page, url, { waitUntil = 'load', timeout = 30000, tries = 3 } = {}) {
  let lastErr;
  for (let attempt = 1; attempt <= tries; attempt++) {
    try {
      await page.goto(url, { waitUntil, timeout });
      return;
    } catch (err) {
      lastErr = err;
      emit(`flow: navigate ${url} failed (try ${attempt}/${tries}) — ${String(err.message || err).slice(0, 120)}`);
      if (attempt < tries) await page.waitForTimeout(1500 * attempt);
    }
  }
  throw lastErr;
}

// dismiss cookie banners / onboarding modals that overlay the first step (zeus-os e2e-lib)
const OVERLAY_LABELS = [
  'accept all', 'accept cookies', 'accept', 'i agree', 'agree', 'got it', 'ok', 'okay',
  'dismiss', 'no thanks', 'maybe later', 'skip', 'skip tour', 'close', 'continue', 'allow all',
];
async function dismissOverlays(page) {
  for (let round = 0; round < 3; round++) {
    let clicked = false;
    for (const label of OVERLAY_LABELS) {
      const btn = page.getByRole('button', { name: new RegExp('^\\s*' + escapeRe(label) + '\\s*$', 'i') }).first();
      try {
        if ((await btn.count()) && (await btn.isVisible())) {
          await btn.click({ timeout: 2000 });
          emit(`flow: dismissed overlay ("${label}")`);
          await page.waitForTimeout(250);
          clicked = true;
          break;
        }
      } catch { /* ignore */ }
    }
    // common close-icon patterns + Escape as a fallback
    if (!clicked) {
      const closeIcon = page.locator('[aria-label*="close" i], [class*="cookie" i] button, [class*="consent" i] button').first();
      try {
        if ((await closeIcon.count()) && (await closeIcon.isVisible())) {
          await closeIcon.click({ timeout: 1500 });
          clicked = true;
        }
      } catch { /* ignore */ }
    }
    if (!clicked) { await page.keyboard.press('Escape').catch(() => {}); break; }
  }
}

async function tryLogin(page) {
  const user = process.env.ZYVOR_TEST_USER, password = process.env.ZYVOR_TEST_PASSWORD;
  if (!user || !password) return;
  try {
    await gotoRetry(page, base + '/', { waitUntil: 'domcontentloaded', timeout: 30000, tries: 3 });
    await dismissOverlays(page);
    const pass = page.locator('input[type="password"]').first();
    if ((await pass.count()) > 0) {
      await page.locator('input[type="email"], input[name*="user" i], input[name*="email" i], input[type="text"]').first().fill(user, { timeout: 5000 });
      await pass.fill(password, { timeout: 5000 });
      await Promise.all([
        page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {}),
        page.locator('button[type="submit"], input[type="submit"], button:has-text("sign in"), button:has-text("log in")').first().click({ timeout: 5000 }),
      ]);
      emit(`flow: logged in as ${user}`);
      await dismissOverlays(page);
    }
  } catch (err) { emit(`flow: login skipped (${err})`); }
}

async function runStep(page, step, n) {
  const { action, target, value, assertion } = step;
  const desc = describe(step);
  switch (action) {
    case 'goto': {
      const url = /^https?:/.test(target) ? target : base + (target?.startsWith('/') ? target : '/' + (target || ''));
      await gotoRetry(page, url, { waitUntil: 'load', timeout: 30000, tries: 3 });
      await page.waitForLoadState('domcontentloaded').catch(() => {});
      await dismissOverlays(page);
      break;
    }
    case 'click': {
      const byRole = page.getByRole('button', { name: new RegExp(escapeRe(target), 'i') }).first();
      const byLink = page.getByRole('link', { name: new RegExp(escapeRe(target), 'i') }).first();
      const byText = page.getByText(target, { exact: false }).first();
      if (await byRole.count()) await byRole.click({ timeout: 10000 });
      else if (await byLink.count()) await byLink.click({ timeout: 10000 });
      else if (await byText.count()) await byText.click({ timeout: 10000 });
      else await page.locator(target).first().click({ timeout: 10000 });
      await page.waitForTimeout(400);
      break;
    }
    case 'fill': {
      const val = value ?? '';
      const byLabel = page.getByLabel(new RegExp(escapeRe(target), 'i')).first();
      const byPh = page.getByPlaceholder(new RegExp(escapeRe(target), 'i')).first();
      if (await byLabel.count()) await byLabel.fill(val, { timeout: 8000 });
      else if (await byPh.count()) await byPh.fill(val, { timeout: 8000 });
      else await page.locator(`input[name*="${target}" i], textarea[name*="${target}" i], ${target}`).first().fill(val, { timeout: 8000 });
      break;
    }
    case 'press':
      await page.keyboard.press(value || 'Enter');
      break;
    case 'wait':
      if (target) await page.waitForSelector(target, { timeout: 15000 });
      else await page.waitForTimeout(Number(value) || 1500);
      break;
    case 'assert': {
      const text = assertion || target;
      if (/^https?:|^\//.test(text || '')) {
        await page.waitForURL(new RegExp(escapeRe(text)), { timeout: 10000 });
      } else if (text) {
        const loc = page.getByText(text, { exact: false }).first();
        await loc.waitFor({ state: 'visible', timeout: 10000 });
      } else {
        await page.getByRole('heading').first().waitFor({ state: 'visible', timeout: 10000 });
      }
      break;
    }
    case 'assert_not': {
      // text/element must NOT be visible — pass if hidden or absent within the window
      const text = assertion || target;
      const loc = page.getByText(text, { exact: false }).first();
      const deadline = Date.now() + 8000;
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const cnt = await loc.count().catch(() => 0);
        const vis = cnt ? await loc.isVisible().catch(() => false) : false;
        if (!vis) break;
        if (Date.now() > deadline) throw new Error(`expected "${text}" to be absent, but it is visible`);
        await page.waitForTimeout(250);
      }
      break;
    }
    case 'assert_count': {
      // target = selector, value = expected integer count
      const want = Number(value);
      const got = await page.locator(target).count();
      if (got !== want) throw new Error(`expected ${want} of "${target}", found ${got}`);
      break;
    }
    case 'assert_value': {
      // target = field, value = expected input value
      const byLabel = page.getByLabel(new RegExp(escapeRe(target), 'i')).first();
      const field = (await byLabel.count()) ? byLabel : page.locator(`input[name*="${target}" i], textarea[name*="${target}" i], ${target}`).first();
      const got = await field.inputValue({ timeout: 8000 });
      if (String(got) !== String(value ?? '')) throw new Error(`expected ${target} = "${value}", got "${got}"`);
      break;
    }
    default:
      throw new Error(`unknown action: ${action}`);
  }
  // runtime-error gate (zeus-os failure-snippet pattern)
  const body = (await page.textContent('body').catch(() => '')) || '';
  const snip = FAIL_SNIPPETS.find((s) => body.includes(s));
  if (snip) throw new Error(`runtime error on page: "${snip}"`);
}

function describe(step) {
  const { action, target, value, assertion } = step;
  if (action === 'goto') return `go to ${target || '/'}`;
  if (action === 'click') return `click "${target}"`;
  if (action === 'fill') return `fill ${target} = "${value}"`;
  if (action === 'press') return `press ${value}`;
  if (action === 'wait') return `wait ${target || (value || '') + 'ms'}`;
  if (action === 'assert') return `assert "${assertion || target}"`;
  if (action === 'assert_not') return `assert NOT "${assertion || target}"`;
  if (action === 'assert_count') return `assert count "${target}" = ${value}`;
  if (action === 'assert_value') return `assert ${target} value = "${value}"`;
  return action;
}
function escapeRe(s) { return String(s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const ctxOpts = { ignoreHTTPSErrors: process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true', viewport: { width: 1440, height: 900 } };
  fs.mkdirSync(outDir, { recursive: true });
  if (record) ctxOpts.recordVideo = { dir: outDir, size: { width: 1440, height: 900 } };
  const context = await browser.newContext(ctxOpts);
  // Playwright trace — time-travel debugger (DOM/network/console per step)
  const wantTrace = flow.trace !== false;
  if (wantTrace) {
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true }).catch(() => {});
  }
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e.message || e)));

  await tryLogin(page);

  const results = [];
  let passed = 0, failed = 0;
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const desc = describe(step);
    emit(`▶ step ${i + 1}/${steps.length}: ${desc}`);
    const before = pageErrors.length;
    let status = 'passed', error = '';
    try {
      await runStep(page, step, i + 1);
      if (pageErrors.length > before) throw new Error(`console: ${pageErrors[before]}`);
      emit(`✓ step ${i + 1}: ${desc}`);
      passed++;
    } catch (err) {
      status = 'failed';
      error = String(err.message || err).slice(0, 300);
      failed++;
      emit(`✗ step ${i + 1}: ${desc} — ${error}`);
    }
    let shot = '';
    try {
      const f = `step-${String(i + 1).padStart(2, '0')}-${slug(desc)}.png`;
      await page.screenshot({ path: path.join(outDir, f) });
      shot = f;
    } catch { /* ignore */ }
    results.push({ n: i + 1, action: step.action, desc, status, error, shot });
    if (status === 'failed' && flow.stop_on_fail) break;
  }

  // stop trace before closing the context
  let traceFile = '';
  if (wantTrace) {
    try {
      traceFile = 'trace.zip';
      await context.tracing.stop({ path: path.join(outDir, traceFile) });
    } catch { traceFile = ''; }
  }

  // finalize video: close context THEN saveAs (Playwright writes on close)
  let videoFile = '';
  const video = record ? page.video() : null;
  await context.close();
  if (video) {
    try {
      videoFile = 'journey.webm';
      await video.saveAs(path.join(outDir, videoFile));
      // remove Playwright's raw hash-named original, keep only journey.webm
      for (const f of fs.readdirSync(outDir)) {
        if (f.endsWith('.webm') && f !== videoFile) fs.rmSync(path.join(outDir, f), { force: true });
      }
    } catch { videoFile = ''; }
  }
  await browser.close();

  process.stdout.write(JSON.stringify({ base, passed, failed, total: steps.length, steps: results, video: videoFile, trace: traceFile }));
}

main().catch((err) => { console.error(err); process.exit(1); });
