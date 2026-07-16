/**
 * Agentic browser runner — the browser half of the "AI tester".
 *
 * Drives a real browser to accomplish an English GOAL. It does NOT decide what
 * to do: each turn it OBSERVES the page (visible interactive elements, tagged
 * with a stable data-zyvor-idx) and emits that to stdout, then reads one ACTION
 * (chosen by the Python LLM decider) from stdin and executes it. Loop until the
 * decider says `done` or maxSteps is hit. Records video + trace of the journey.
 *
 * Protocol (line-delimited JSON over stdio):
 *   stdout  @@OBS@@ {step,url,title,elements:[{i,role,name,value,enabled}],texts,note}
 *   stdin   {action:"click|fill|select|press|goto|wait_until|assert|done", i, value, text, timeout, success, summary, reason}
 *   stdout  @@RESULT@@ {goal,passed,steps:[...],video,trace,done_summary}
 * Human-readable progress → stderr.
 *
 * Usage: node ai-flow.mjs <configJsonFile> <outDir>
 *   config: { url, goal, session, insecure, max_steps }
 */

import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import readline from 'readline';

const cfgFile = process.argv[2];
const outDir = process.argv[3];
if (!cfgFile || !outDir) { console.error('Usage: node ai-flow.mjs <configJsonFile> <outDir>'); process.exit(2); }
const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf-8'));
const startUrl = cfg.url || '';
let base = startUrl.replace(/\/$/, '');
try { base = new URL(startUrl).origin; } catch { /* keep */ }
const MAX_STEPS = Math.max(1, Math.min(cfg.max_steps || 20, 40));
const emit = (m) => console.error(m);
const send = (tag, obj) => process.stdout.write(tag + ' ' + JSON.stringify(obj) + '\n');

// one-action-at-a-time reader over stdin
const rl = readline.createInterface({ input: process.stdin });
const _inbox = [];
let _waiter = null;
rl.on('line', (line) => { if (_waiter) { _waiter(line); _waiter = null; } else _inbox.push(line); });
function nextAction() {
  return new Promise((resolve) => { if (_inbox.length) resolve(_inbox.shift()); else _waiter = resolve; });
}

// tag visible interactive elements with data-zyvor-idx and return a compact list
async function observe(page) {
  return page.evaluate(() => {
    const sel = 'button, a[href], input, select, textarea, [role=button], [role=tab], [role=option], [role=menuitem], [role=switch], [role=checkbox]';
    const out = [];
    let i = 0;
    const seen = new Set();
    for (const el of document.querySelectorAll(sel)) {
      if (seen.has(el)) continue;
      const r = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      if (r.width < 2 || r.height < 2 || style.visibility === 'hidden' || style.display === 'none') continue;
      seen.add(el);
      el.setAttribute('data-zyvor-idx', String(i));
      const role = el.getAttribute('role') || el.tagName.toLowerCase();
      const name = (el.getAttribute('aria-label') || el.getAttribute('placeholder')
        || (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA' ? (el.labels && el.labels[0] ? el.labels[0].innerText : '') : el.innerText)
        || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 80);
      const type = el.getAttribute('type') || '';
      const enabled = !el.disabled && el.getAttribute('aria-disabled') !== 'true';
      out.push({ i, role: type && role === 'input' ? `input:${type}` : role, name, value: (el.value || '').slice(0, 40), enabled });
      i++;
      if (i >= 60) break;
    }
    // salient page text: headings + visible error/status text
    const texts = [];
    for (const h of document.querySelectorAll('h1,h2,h3,[role=heading]')) {
      const t = (h.innerText || '').trim().replace(/\s+/g, ' ');
      if (t) texts.push('heading: ' + t.slice(0, 80));
      if (texts.length >= 6) break;
    }
    for (const e of document.querySelectorAll('[class*="error" i],[role=alert],[class*="toast" i]')) {
      const t = (e.innerText || '').trim().replace(/\s+/g, ' ');
      if (t && t.length < 160) texts.push('alert: ' + t);
      if (texts.length >= 12) break;
    }
    return { elements: out, texts };
  });
}

async function byIdx(page, i) { return page.locator(`[data-zyvor-idx="${i}"]`).first(); }

// dismiss onboarding/cookie overlays that block the app (zeus-os shows an onboarding tour)
const OVERLAY_LABELS = ['skip', 'skip tour', 'got it', 'dismiss', 'no thanks', 'maybe later', 'close', 'accept', 'continue', 'ok'];
async function dismissOverlays(page) {
  for (let round = 0; round < 2; round++) {
    let clicked = false;
    for (const label of OVERLAY_LABELS) {
      const btn = page.getByRole('button', { name: new RegExp('^\\s*' + label + '\\s*$', 'i') }).first();
      try {
        if ((await btn.count()) && (await btn.isVisible())) { await btn.click({ timeout: 1500 }); clicked = true; await page.waitForTimeout(300); break; }
      } catch { /* ignore */ }
    }
    if (!clicked) { await page.keyboard.press('Escape').catch(() => {}); break; }
  }
}

// let async content (modals, skeletons) settle before observing
async function settle(page) {
  await page.locator('[class*="skeleton" i], .animate-pulse').first().waitFor({ state: 'hidden', timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(1200);
  await dismissOverlays(page);
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const ctxOpts = { ignoreHTTPSErrors: cfg.insecure === true || process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true',
                    viewport: { width: 1440, height: 900 } };
  fs.mkdirSync(outDir, { recursive: true });
  ctxOpts.recordVideo = { dir: outDir, size: { width: 1440, height: 900 } };
  let savedSessionStorage = null, savedToken = '';
  if (cfg.session && fs.existsSync(cfg.session)) {
    try {
      const st = JSON.parse(fs.readFileSync(cfg.session, 'utf-8'));
      ctxOpts.storageState = { cookies: st.cookies || [], origins: st.origins || [] };
      savedSessionStorage = st._sessionStorage || null;
      savedToken = st._token || '';
      emit('ai: reusing saved session');
    } catch { /* ignore */ }
  }
  const context = await browser.newContext(ctxOpts);
  if (savedSessionStorage || savedToken) {
    await context.addInitScript(({ json, token }) => {
      try { const d = JSON.parse(json || '{}'); for (const k in d) sessionStorage.setItem(k, d[k]); } catch {}
      // token storage key is product-specific — set it under all common names, both storages
      if (token) {
        const keys = ['token', 'access_token', 'auth_token', 'authToken', 'jwt', 'id_token', 'zeus_os_token', 'zyvor_token', 'apiToken'];
        for (const k of keys) { try { localStorage.setItem(k, token); } catch {} try { sessionStorage.setItem(k, token); } catch {} }
      }
    }, { json: savedSessionStorage, token: savedToken });
  }
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true }).catch(() => {});
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e.message || e)));

  await page.goto(startUrl, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch((e) => emit('ai: initial goto failed ' + e));
  await settle(page);

  const steps = [];
  let passed = false, doneSummary = '';
  for (let step = 1; step <= MAX_STEPS; step++) {
    await settle(page);
    let obs;
    try { obs = await observe(page); } catch (e) { obs = { elements: [], texts: ['observe failed: ' + e] }; }
    send('@@OBS@@', { step, url: page.url().replace(base, '') || '/', title: (await page.title().catch(() => '')) , elements: obs.elements, texts: obs.texts, errors: pageErrors.slice(-2) });

    const raw = await nextAction();
    let act;
    try { act = JSON.parse(raw); } catch { emit('ai: bad action json'); continue; }
    const a = act.action;
    emit(`▶ step ${step}: ${a}${act.reason ? ' — ' + act.reason : ''}`);
    let status = 'ok', error = '';
    try {
      if (a === 'done') { passed = act.success !== false; doneSummary = act.summary || ''; steps.push({ n: step, action: a, reason: act.reason || act.summary || '', status: 'ok' }); break; }
      else if (a === 'click') { const el = await byIdx(page, act.i); await el.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {}); await el.click({ timeout: 8000 }).catch(async () => el.click({ timeout: 5000, force: true })); }
      else if (a === 'fill') { const el = await byIdx(page, act.i); await el.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {}); await el.fill(String(act.value ?? ''), { timeout: 8000 }); }
      else if (a === 'select') { await (await byIdx(page, act.i)).selectOption({ label: String(act.value) }).catch(async () => (await byIdx(page, act.i)).selectOption(String(act.value))); }
      else if (a === 'press') { await page.keyboard.press(act.value || act.text || 'Enter'); }
      else if (a === 'goto') { await page.goto(/^https?:/.test(act.value || act.text) ? (act.value || act.text) : base + (act.value || act.text || '/'), { waitUntil: 'domcontentloaded', timeout: 30000 }); }
      else if (a === 'wait_until') {
        const t = act.text || act.value; const to = Math.min(act.timeout || 30000, 180000);
        await page.getByText(t, { exact: false }).first().waitFor({ state: 'visible', timeout: to });
      }
      else if (a === 'assert') {
        const t = act.text || act.value;
        if (/^https?:|^\//.test(t)) await page.waitForURL(new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), { timeout: 8000 });
        else await page.getByText(t, { exact: false }).first().waitFor({ state: 'visible', timeout: 8000 });
      }
      else { error = `unknown action ${a}`; status = 'failed'; }
    } catch (e) { status = 'failed'; error = String(e.message || e).slice(0, 200); }

    let shot = '';
    try { const f = `step-${String(step).padStart(2, '0')}-${a}.png`; await page.screenshot({ path: path.join(outDir, f) }); shot = f; } catch { /* ignore */ }
    steps.push({ n: step, action: a, target: act.i, value: act.value, reason: act.reason || '', status, error, shot,
                 desc: `${a}${act.value ? ' "' + String(act.value).slice(0, 40) + '"' : ''}${act.reason ? ' — ' + act.reason : ''}` });
    if (status === 'ok') emit(`✓ step ${step}: ${a}`); else emit(`✗ step ${step}: ${a} — ${error}`);
  }
  if (!doneSummary && steps.length >= MAX_STEPS) emit('ai: hit max steps without done');

  let traceFile = '';
  try { traceFile = 'trace.zip'; await context.tracing.stop({ path: path.join(outDir, traceFile) }); } catch { traceFile = ''; }
  let videoFile = '';
  const video = page.video();
  await context.close();
  if (video) { try { videoFile = 'journey.webm'; await video.saveAs(path.join(outDir, videoFile)); for (const f of fs.readdirSync(outDir)) if (f.endsWith('.webm') && f !== videoFile) fs.rmSync(path.join(outDir, f), { force: true }); } catch { videoFile = ''; } }
  await browser.close();

  send('@@RESULT@@', { goal: cfg.goal, passed, done_summary: doneSummary, steps, total: steps.length, video: videoFile, trace: traceFile });
  process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
