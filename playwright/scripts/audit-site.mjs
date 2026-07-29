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
 * Site-audit — BFS crawl + per-page QA checks. Emits JSON to stdout.
 *
 * Usage:
 *   node audit-site.mjs <baseUrl> [maxPages] [checks] [maxDepth]
 *   checks = comma list of: a11y,links,seo,console,perf,headers,responsive
 *
 * Env: ZYVOR_IGNORE_HTTPS_ERRORS, ZYVOR_NO_SANDBOX,
 *      ZYVOR_TEST_USER/ZYVOR_TEST_PASSWORD (best-effort login),
 *      ZYVOR_AUDIT_REPORTS_DIR (for responsive screenshots).
 */

import { chromium } from '@playwright/test';
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../..');

const baseUrl = process.argv[2] || process.env.ZYVOR_BASE_URL || 'https://zyvor.dev';
const maxPages = parseInt(process.argv[3] || '20', 10);
const checks = (process.argv[4] || 'a11y,links,seo,console,perf,headers')
  .split(',').map((s) => s.trim()).filter(Boolean);
const maxDepth = parseInt(process.argv[5] || '2', 10);
const wantResponsive = checks.includes('responsive');
const reportsDir = process.env.ZYVOR_AUDIT_REPORTS_DIR || path.join(repoRoot, 'reports');

let axeSource = null;
if (checks.includes('a11y')) {
  try {
    axeSource = fs.readFileSync(require.resolve('axe-core'), 'utf-8');
  } catch {
    console.error('audit: axe-core not installed — a11y check skipped');
  }
}

function slug(text) {
  return (text || 'page').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'page';
}
function normalizeUrl(href, origin) {
  try {
    const url = new URL(href, origin);
    if (url.origin !== origin) return null;
    url.hash = '';
    return url.pathname.replace(/\/+$/, '') || '/';
  } catch { return null; }
}
const emit = (msg) => console.error(msg); // stderr = live progress

async function checkA11y(page) {
  if (!axeSource) return null;
  try {
    await page.evaluate(axeSource);
    const res = await page.evaluate(async () => await window.axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] },
    }));
    const violations = res.violations || [];
    const byImpact = { critical: 0, serious: 0, moderate: 0, minor: 0 };
    const issues = [];
    for (const v of violations) {
      byImpact[v.impact] = (byImpact[v.impact] || 0) + v.nodes.length;
      issues.push(`[${v.impact}] ${v.id}: ${v.help} (${v.nodes.length})`);
    }
    const status = byImpact.critical || byImpact.serious ? 'fail' : violations.length ? 'warn' : 'ok';
    return { status, score: violations.length, issues: issues.slice(0, 15), byImpact };
  } catch (err) {
    return { status: 'warn', score: 0, issues: [`axe error: ${err}`.slice(0, 120)] };
  }
}

async function checkLinks(page, origin) {
  const urls = await page.$$eval('a[href], img[src]', (els) =>
    els.map((e) => e.getAttribute('href') || e.getAttribute('src')).filter(Boolean));
  const seen = new Set();
  const targets = [];
  for (const u of urls) {
    try {
      const abs = new URL(u, location.href).href;
      if (abs.startsWith('http') && !seen.has(abs)) { seen.add(abs); targets.push(abs); }
    } catch { /* skip */ }
  }
  const broken = [];
  const ctx = page.context();
  const cap = targets.slice(0, 40);
  await Promise.all(cap.map(async (u) => {
    try {
      const resp = await ctx.request.head(u, { timeout: 10000, failOnStatusCode: false });
      let status = resp.status();
      if (status === 405 || status === 501) {
        const g = await ctx.request.get(u, { timeout: 10000, failOnStatusCode: false });
        status = g.status();
      }
      if (status >= 400) broken.push(`${status} ${u}`);
    } catch (err) {
      broken.push(`ERR ${u}`);
    }
  }));
  const status = broken.length ? 'fail' : 'ok';
  return { status, score: broken.length, checked: cap.length, issues: broken.slice(0, 15) };
}

async function checkSeo(page) {
  const data = await page.evaluate(() => {
    const meta = (n) => document.querySelector(`meta[name="${n}"]`)?.content
      || document.querySelector(`meta[property="${n}"]`)?.content || '';
    return {
      title: document.title || '',
      description: meta('description'),
      canonical: document.querySelector('link[rel="canonical"]')?.href || '',
      ogTitle: meta('og:title'), ogImage: meta('og:image'),
      h1: document.querySelectorAll('h1').length,
      lang: document.documentElement.getAttribute('lang') || '',
      viewport: !!document.querySelector('meta[name="viewport"]'),
    };
  });
  const issues = [];
  if (!data.title) issues.push('missing <title>');
  else if (data.title.length > 60) issues.push(`title too long (${data.title.length})`);
  if (!data.description) issues.push('missing meta description');
  if (!data.canonical) issues.push('no canonical link');
  if (!data.ogTitle || !data.ogImage) issues.push('incomplete Open Graph tags');
  if (data.h1 === 0) issues.push('no <h1>');
  else if (data.h1 > 1) issues.push(`${data.h1} <h1> elements`);
  if (!data.lang) issues.push('no lang attribute');
  if (!data.viewport) issues.push('no viewport meta');
  const status = issues.length >= 4 ? 'fail' : issues.length ? 'warn' : 'ok';
  return { status, score: issues.length, issues };
}

async function checkPerf(page) {
  const t = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const res = performance.getEntriesByType('resource');
    const bytes = res.reduce((a, r) => a + (r.transferSize || 0), 0);
    return nav ? {
      domContentLoaded: Math.round(nav.domContentLoadedEventEnd),
      load: Math.round(nav.loadEventEnd || nav.duration),
      resources: res.length,
      transferKB: Math.round(bytes / 1024),
    } : null;
  });
  if (!t) return { status: 'warn', score: 0, issues: ['no navigation timing'] };
  const issues = [];
  if (t.load > 5000) issues.push(`slow load ${t.load}ms`);
  if (t.transferKB > 4096) issues.push(`heavy page ${t.transferKB}KB`);
  if (t.resources > 150) issues.push(`${t.resources} requests`);
  const status = t.load > 8000 || t.transferKB > 8192 ? 'fail' : issues.length ? 'warn' : 'ok';
  return { status, score: t.load, metrics: t, issues };
}

function checkHeaders(headers) {
  const want = {
    'content-security-policy': 'CSP',
    'strict-transport-security': 'HSTS',
    'x-content-type-options': 'X-Content-Type-Options',
    'x-frame-options': 'X-Frame-Options',
    'referrer-policy': 'Referrer-Policy',
  };
  const missing = [];
  for (const [h, label] of Object.entries(want)) if (!headers[h]) missing.push(label);
  const status = missing.length >= 4 ? 'fail' : missing.length ? 'warn' : 'ok';
  return { status, score: missing.length, issues: missing.map((m) => `missing ${m}`) };
}

async function tryLogin(page, origin) {
  const user = process.env.ZYVOR_TEST_USER, password = process.env.ZYVOR_TEST_PASSWORD;
  if (!user || !password) return;
  try {
    await page.goto(origin + '/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    const pass = page.locator('input[type="password"]').first();
    if ((await pass.count()) > 0) {
      await page.locator('input[type="email"], input[name*="user" i], input[name*="email" i], input[type="text"]').first().fill(user, { timeout: 5000 });
      await pass.fill(password, { timeout: 5000 });
      await Promise.all([
        page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {}),
        page.locator('button[type="submit"], input[type="submit"], button:has-text("sign in"), button:has-text("log in")').first().click({ timeout: 5000 }),
      ]);
      emit(`audit: logged in as ${user}`);
    }
  } catch (err) { emit(`audit: login skipped (${err})`); }
}

async function audit() {
  const origin = new URL(baseUrl).origin;
  const browser = await chromium.launch({
    headless: true,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const context = await browser.newContext({
    ignoreHTTPSErrors: process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true',
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => consoleErrors.push(String(e).slice(0, 200)));
  const netErrors = [];
  page.on('response', (r) => { if (r.status() >= 400) netErrors.push(`${r.status()} ${r.url()}`.slice(0, 200)); });

  await tryLogin(page, origin);

  const queue = [{ path: '/', depth: 0 }];
  const visited = new Set();
  const pages = [];

  while (queue.length > 0 && visited.size < maxPages) {
    const { path: routePath, depth } = queue.shift();
    if (visited.has(routePath)) continue;
    visited.add(routePath);
    const url = origin + (routePath === '/' ? '/' : routePath);
    consoleErrors.length = 0; netErrors.length = 0;

    try {
      const resp = await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      const headers = resp ? resp.headers() : {};
      const status = resp?.status() ?? 0;
      const title = (await page.title()) || routePath;
      emit(`audit: ${routePath} (HTTP ${status})`);

      const result = { path: routePath, url, title: title.trim(), status, checks: {} };
      if (checks.includes('a11y')) result.checks.a11y = await checkA11y(page);
      if (checks.includes('links')) result.checks.links = await checkLinks(page, origin);
      if (checks.includes('seo')) result.checks.seo = await checkSeo(page);
      if (checks.includes('perf')) result.checks.perf = await checkPerf(page);
      if (checks.includes('headers')) result.checks.headers = checkHeaders(headers);
      if (checks.includes('console')) {
        const issues = [...new Set([...consoleErrors, ...netErrors])].slice(0, 15);
        result.checks.console = { status: issues.length ? 'fail' : 'ok', score: issues.length, issues };
      }
      if (wantResponsive) {
        const shots = [];
        for (const [w, h, label] of [[390, 844, 'mobile'], [820, 1180, 'tablet'], [1440, 900, 'desktop']]) {
          await page.setViewportSize({ width: w, height: h });
          const dir = path.join(reportsDir, 'artifacts', 'audit-shots');
          fs.mkdirSync(dir, { recursive: true });
          const f = path.join(dir, `${slug(routePath)}-${label}.png`);
          await page.screenshot({ path: f, fullPage: false }).catch(() => {});
          shots.push(`/reports/artifacts/audit-shots/${path.basename(f)}`);
        }
        await page.setViewportSize({ width: 1280, height: 720 });
        result.checks.responsive = { status: 'ok', score: 0, shots, issues: [] };
      }
      pages.push(result);

      if (depth < maxDepth) {
        const hrefs = await page.$$eval('a[href]', (a) => a.map((x) => x.getAttribute('href')).filter(Boolean));
        for (const href of hrefs) {
          const n = normalizeUrl(href, origin);
          if (n && !visited.has(n)) queue.push({ path: n, depth: depth + 1 });
        }
      }
    } catch (err) {
      pages.push({ path: routePath, url, title: routePath, status: 0, error: String(err).slice(0, 200), checks: {} });
      emit(`audit: ${routePath} ERROR ${err}`);
    }
  }
  await browser.close();

  const summary = { pages: pages.length, checks, byCheck: {} };
  for (const c of checks) {
    summary.byCheck[c] = { ok: 0, warn: 0, fail: 0 };
    for (const p of pages) {
      const s = p.checks[c]?.status;
      if (s) summary.byCheck[c][s]++;
    }
  }
  process.stdout.write(JSON.stringify({ base: baseUrl, pages, summary }));
}

audit().catch((err) => { console.error(err); process.exit(1); });
