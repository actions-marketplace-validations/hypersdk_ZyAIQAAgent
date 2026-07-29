import { test as base, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { writeCoverageArtifact } from '../utils/coverage';

export type LogFixtures = {
  consoleLogs: string[];
  networkErrors: string[];
  apiCalls: { url: string; method: string; status: number }[];
};

const repoRoot = path.resolve(__dirname, '../..');
const authFile = path.join(__dirname, '../.auth/user.json');
const v8Enabled = () => process.env.ENABLE_V8_COVERAGE === 'true';

/**
 * Re-inject sessionStorage / token that Playwright storageState omits.
 * Matches the enrichment written by auth.setup.ts and auth-probe.mjs.
 */
async function reinjectSessionExtras(page: import('@playwright/test').Page) {
  if (process.env.ENABLE_AUTH_SETUP !== 'true' || !fs.existsSync(authFile)) return;
  try {
    const state = JSON.parse(fs.readFileSync(authFile, 'utf-8'));
    const json = state._sessionStorage || null;
    const token = state._token || '';
    if (!json && !token) return;
    await page.addInitScript(
      ({ json, token }: { json: string | null; token: string }) => {
        try {
          const d = JSON.parse(json || '{}');
          for (const k in d) sessionStorage.setItem(k, d[k]);
        } catch {
          /* ignore */
        }
        if (token) {
          const keys = [
            'token',
            'access_token',
            'auth_token',
            'authToken',
            'jwt',
            'id_token',
            'zeus_os_token',
            'zyvor_token',
            'apiToken',
          ];
          for (const k of keys) {
            try {
              localStorage.setItem(k, token);
            } catch {
              /* ignore */
            }
            try {
              sessionStorage.setItem(k, token);
            } catch {
              /* ignore */
            }
          }
        }
      },
      { json, token },
    );
  } catch {
    /* ignore corrupt auth file */
  }
}

export const test = base.extend<LogFixtures>({
  page: async ({ page }, use, testInfo) => {
    await reinjectSessionExtras(page);
    if (v8Enabled()) {
      await page.coverage.startJSCoverage();
    }
    await use(page);
    if (v8Enabled()) {
      const coverage = await page.coverage.stopJSCoverage();
      await writeCoverageArtifact(testInfo, coverage, repoRoot);
    }
  },

  consoleLogs: async ({ page }, use, testInfo) => {
    const logs: string[] = [];
    page.on('console', (msg) => {
      logs.push(`[${msg.type()}] ${msg.text()}`);
    });
    await use(logs);
    await testInfo.attach('console.log', {
      body: logs.join('\n'),
      contentType: 'text/plain',
    });
  },

  networkErrors: async ({ page }, use, testInfo) => {
    const errors: string[] = [];
    page.on('response', (response) => {
      if (response.status() >= 400) {
        errors.push(`${response.status()} ${response.request().method()} ${response.url()}`);
      }
    });
    await use(errors);
    if (errors.length > 0) {
      await testInfo.attach('network-errors.log', {
        body: errors.join('\n'),
        contentType: 'text/plain',
      });
    }
  },

  apiCalls: async ({ page }, use) => {
    const calls: { url: string; method: string; status: number }[] = [];
    page.on('response', (response) => {
      calls.push({
        url: response.url(),
        method: response.request().method(),
        status: response.status(),
      });
    });
    await use(calls);
  },
});

export { expect };
