/**
 * Live-data probe — assert WebSocket / SSE streams are actually live, and that
 * a dashboard's live regions update. Adopts packetwolf's insight: never wait
 * for networkidle on always-live dashboards; use domcontentloaded + per-request
 * latency budget and classify the page.
 *
 * Usage: node realtime-probe.mjs <configJsonFile> <outDir>
 *   config: { url, ws, sse, ticket_url, ticket_query, token, subprotocol_jwt,
 *             expect_messages, window_ms, live_selector, session (storageState path), insecure }
 * Progress → stderr, result JSON → stdout.
 */

import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const cfgFile = process.argv[2];
const outDir = process.argv[3];
if (!cfgFile) { console.error('Usage: node realtime-probe.mjs <configJsonFile> <outDir>'); process.exit(2); }
const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf-8'));
const base = (cfg.url || '').replace(/\/$/, '');
const emit = (m) => console.error(m);
const SLOW_MS = Number(process.env.ZYVOR_SLOW_MS || '12000');

function absWs(u) {
  if (/^wss?:/.test(u)) return u;
  const b = base.replace(/^http/, 'ws');
  return b + (u.startsWith('/') ? u : '/' + u);
}
function absHttp(u) { return /^https?:/.test(u) ? u : base + (u.startsWith('/') ? u : '/' + u); }

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const ctxOpts = { ignoreHTTPSErrors: cfg.insecure === true || process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true' };
  if (cfg.session && fs.existsSync(cfg.session)) { ctxOpts.storageState = cfg.session; emit('realtime: reusing saved session'); }
  const context = await browser.newContext(ctxOpts);
  const page = await context.newPage();

  const result = { url: base, checks: [] };
  const add = (name, ok, detail) => { result.checks.push({ name, ok, detail }); emit(`${ok ? '✓' : '✗'} ${name}${detail ? ' — ' + detail : ''}`); };

  // land on the app first so cookies/session apply for in-page sockets
  try { await page.goto(base + '/', { waitUntil: 'domcontentloaded', timeout: 30000 }); } catch { /* continue */ }

  // optional one-time ticket (veyron ws_ticket pattern)
  let ticket = '';
  if (cfg.ticket_url) {
    try {
      const resp = await page.request.get(absHttp(cfg.ticket_url));
      const j = await resp.json().catch(() => ({}));
      ticket = j.ticket || j.token || '';
      add('issue ws ticket', !!ticket, ticket ? 'acquired' : `status ${resp.status()}`);
    } catch (e) { add('issue ws ticket', false, String(e).slice(0, 120)); }
  }

  // ── WebSocket check (connect in-page so cookies apply) ──
  if (cfg.ws) {
    let wsUrl = absWs(cfg.ws);
    const q = [];
    if (ticket) q.push(`${cfg.ticket_query || 'ticket'}=${encodeURIComponent(ticket)}`);
    if (cfg.token && !cfg.subprotocol_jwt) q.push(`token=${encodeURIComponent(cfg.token)}`);
    if (q.length) wsUrl += (wsUrl.includes('?') ? '&' : '?') + q.join('&');
    const protocols = cfg.subprotocol_jwt && cfg.token ? ['access_token', cfg.token] : undefined;

    const wsRes = await page.evaluate(async ({ wsUrl, protocols, expect, windowMs }) => {
      return await new Promise((resolve) => {
        let count = 0; const sample = []; let opened = false; let reconnected = false;
        const done = (extra) => resolve({ opened, count, sample, reconnected, ...extra });
        let ws;
        const open = (isReconnect) => {
          try { ws = protocols ? new WebSocket(wsUrl, protocols) : new WebSocket(wsUrl); }
          catch (e) { return done({ error: String(e) }); }
          ws.onopen = () => { opened = true; if (isReconnect) reconnected = true; };
          ws.onmessage = (ev) => { count++; if (sample.length < 3) sample.push(String(ev.data).slice(0, 200)); };
          ws.onerror = () => {};
        };
        open(false);
        // after half the window, force a close to test reconnect
        setTimeout(() => { try { if (ws) ws.close(); } catch {} setTimeout(() => open(true), 300); }, Math.max(1000, windowMs / 2));
        setTimeout(() => { try { if (ws) ws.close(); } catch {} done({}); }, windowMs);
      });
    }, { wsUrl, protocols, expect: cfg.expect_messages, windowMs: cfg.window_ms || 15000 });

    add('ws connect', !!wsRes.opened, wsRes.error || wsUrl);
    add(`ws receives ≥${cfg.expect_messages} messages`, wsRes.count >= cfg.expect_messages, `${wsRes.count} received`);
    add('ws reconnect', !!wsRes.reconnected, wsRes.reconnected ? 'reconnected' : 'no reconnect');
    result.ws = { url: wsUrl, opened: wsRes.opened, messages: wsRes.count, reconnected: wsRes.reconnected, sample: wsRes.sample };
  }

  // ── SSE check ──
  if (cfg.sse) {
    const sseUrl = absHttp(cfg.sse) + (cfg.token ? (cfg.sse.includes('?') ? '&' : '?') + `token=${encodeURIComponent(cfg.token)}` : '');
    const sseRes = await page.evaluate(async ({ sseUrl, windowMs }) => {
      return await new Promise((resolve) => {
        let count = 0; const sample = []; let opened = false;
        let es;
        try { es = new EventSource(sseUrl); } catch (e) { return resolve({ opened, count, sample, error: String(e) }); }
        es.onopen = () => { opened = true; };
        es.onmessage = (ev) => { count++; if (sample.length < 3) sample.push(String(ev.data).slice(0, 200)); };
        es.onerror = () => {};
        setTimeout(() => { try { es.close(); } catch {} resolve({ opened, count, sample }); }, windowMs);
      });
    }, { sseUrl, windowMs: cfg.window_ms || 15000 });
    add('sse connect', !!sseRes.opened, sseRes.error || sseUrl);
    add(`sse receives ≥${cfg.expect_messages} messages`, sseRes.count >= cfg.expect_messages, `${sseRes.count} received`);
    result.sse = { url: sseUrl, opened: sseRes.opened, messages: sseRes.count, sample: sseRes.sample };
  }

  // ── browser live-view: does a region update? + latency-budget classify ──
  if (cfg.live_selector) {
    let wsFrames = 0;
    page.on('websocket', (ws) => { ws.on('framereceived', () => { wsFrames++; }); });
    const pending = new Map(); let slow = false; let api5xx = false; let crashed = false;
    page.on('request', (r) => { if (r.url().includes('/api/')) pending.set(r, Date.now()); });
    page.on('requestfinished', (r) => pending.delete(r));
    page.on('response', (r) => { if (r.status() >= 500) api5xx = true; });
    page.on('pageerror', () => { crashed = true; });

    let before = '', after = '';
    try {
      before = (await page.locator(cfg.live_selector).first().textContent({ timeout: 8000 }).catch(() => '')) || '';
    } catch { /* selector absent */ }
    const t0 = Date.now();
    while (Date.now() - t0 < Math.min(cfg.window_ms || 15000, 15000)) {
      await page.waitForTimeout(1000);
      for (const [, started] of pending) if (Date.now() - started > SLOW_MS) { slow = true; break; }
    }
    after = (await page.locator(cfg.live_selector).first().textContent().catch(() => '')) || before;
    const updated = wsFrames > 0 || (before && after && before !== after);
    const cls = crashed ? 'crash' : api5xx ? 'api-5xx' : slow ? 'slow' : 'ok';
    add('live region updates', updated, wsFrames ? `${wsFrames} ws frames` : (updated ? 'text changed' : 'no change'));
    add('page health', cls === 'ok', cls);
    result.live = { selector: cfg.live_selector, ws_frames: wsFrames, updated, classification: cls };
  }

  let shot = '';
  if (outDir) {
    fs.mkdirSync(outDir, { recursive: true });
    try { await page.screenshot({ path: path.join(outDir, 'realtime.png') }); shot = 'realtime.png'; } catch { /* ignore */ }
  }
  await browser.close();

  const passed = result.checks.filter((c) => c.ok).length;
  result.passed = passed;
  result.failed = result.checks.length - passed;
  result.total = result.checks.length;
  result.shot = shot;
  process.stdout.write(JSON.stringify(result));
}

main().catch((e) => { console.error(e); process.exit(1); });
