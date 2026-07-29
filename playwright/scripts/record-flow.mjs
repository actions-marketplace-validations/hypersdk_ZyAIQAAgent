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
 * Headed local flow recorder — click/type in a browser; emit .flow.json steps.
 * Local-only (not for headless Mission Control).
 *
 * Usage: node record-flow.mjs <url> [out.json]
 * Env: ZYVOR_IGNORE_HTTPS_ERRORS, ZYVOR_NO_SANDBOX
 *
 * Interact with the page, then press Ctrl+C (or close the browser) to save.
 */

import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const url = process.argv[2];
const outFile = process.argv[3] || path.join(process.cwd(), 'recorded.flow.json');
if (!url) {
  console.error('Usage: node playwright/scripts/record-flow.mjs <url> [out.json]');
  process.exit(2);
}

const steps = [];
const push = (step) => {
  steps.push(step);
  console.error(`+ ${step.action} ${step.target || step.value || step.assertion || ''}`);
};

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: process.env.ZYVOR_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [],
  });
  const context = await browser.newContext({
    ignoreHTTPSErrors: process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true',
  });
  const page = await context.newPage();

  await page.exposeBinding('__zyvorRecord', (_source, payload) => {
    if (payload && payload.action) push(payload);
  });

  await page.addInitScript(() => {
    const send = (action, target, value, assertion) => {
      try {
        window.__zyvorRecord({ action, target: target || '', value: value || '', assertion: assertion || '' });
      } catch { /* ignore */ }
    };
    document.addEventListener('click', (e) => {
      const el = e.target;
      if (!(el instanceof Element)) return;
      const label =
        el.getAttribute('aria-label') ||
        (el instanceof HTMLElement ? el.innerText : '') ||
        el.getAttribute('name') ||
        el.id ||
        el.tagName;
      send('click', String(label).trim().slice(0, 80));
    }, true);
    document.addEventListener('change', (e) => {
      const el = e.target;
      if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement)) return;
      const name = el.getAttribute('aria-label') || el.name || el.id || 'field';
      if (el instanceof HTMLSelectElement) send('select', name, el.value);
      else if (el.type === 'file') send('upload', name, el.value);
      else send('fill', name, el.value);
    }, true);
  });

  push({ action: 'goto', target: url, value: '', assertion: '' });
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  console.error('Recording… interact with the page, then close the browser window to save.');

  await new Promise((resolve) => {
    browser.on('disconnected', resolve);
  });

  const flow = {
    base: url.replace(/\/$/, ''),
    steps: steps.map((s) => ({
      action: s.action,
      target: s.target || '',
      value: s.value || '',
      assertion: s.assertion || '',
    })),
  };
  fs.writeFileSync(outFile, JSON.stringify(flow, null, 2));
  console.error(`Saved ${flow.steps.length} step(s) → ${outFile}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
