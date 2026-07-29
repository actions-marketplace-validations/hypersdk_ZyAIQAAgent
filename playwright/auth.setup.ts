/**
 * Playwright setup project — login once and write storageState for dependent projects.
 * Enabled when ENABLE_AUTH_SETUP=true and credentials are present.
 */
import { test as setup, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { login, hasAuthCredentials } from './utils/auth';

const AUTH_DIR = path.join(__dirname, '.auth');
const AUTH_FILE = path.join(AUTH_DIR, 'user.json');

setup('authenticate', async ({ page }) => {
  setup.skip(!hasAuthCredentials(), 'No dashboard credentials — skip auth setup');

  fs.mkdirSync(AUTH_DIR, { recursive: true });
  await login(page);
  await expect(page).toHaveURL(/dashboard|home|vm/i, { timeout: 30000 });

  // Capture cookies + localStorage (Playwright), then enrich with sessionStorage + token
  const state = await page.context().storageState();
  const sessionStorage = await page.evaluate(() => {
    const out: Record<string, string> = {};
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k) out[k] = sessionStorage.getItem(k) || '';
    }
    return out;
  });
  const token =
    sessionStorage['token'] ||
    sessionStorage['access_token'] ||
    sessionStorage['auth_token'] ||
    sessionStorage['jwt'] ||
    '';

  const enriched = {
    ...state,
    _sessionStorage: JSON.stringify(sessionStorage),
    _token: token,
  };
  fs.writeFileSync(AUTH_FILE, JSON.stringify(enriched, null, 2));
});
