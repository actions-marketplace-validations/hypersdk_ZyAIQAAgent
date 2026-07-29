import { Locator, Page, expect } from '@playwright/test';

/**
 * Wait for page to be fully loaded and interactive.
 */
export async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForLoadState('networkidle').catch(() => {
    // networkidle may timeout on sites with long-polling; non-fatal
  });
}

/**
 * Assert no critical console errors occurred.
 */
export async function assertNoConsoleErrors(consoleLogs: string[]): Promise<void> {
  const errors = consoleLogs.filter((log) => log.startsWith('[error]'));
  expect(errors, `Console errors: ${errors.join(', ')}`).toHaveLength(0);
}

/**
 * Poll until a locator is visible (eventual UI — VM status, provisioning, etc.).
 * Prefer this over fixed sleeps; wraps Playwright's auto-wait with an explicit budget.
 */
export async function eventuallyVisible(
  locator: Locator,
  opts: { timeout?: number } = {},
): Promise<void> {
  const timeout = opts.timeout ?? 30000;
  await expect(locator).toBeVisible({ timeout });
}

/**
 * Poll until text is gone / hidden (spinners, "Provisioning…").
 */
export async function waitForTextGone(
  page: Page,
  text: string | RegExp,
  opts: { timeout?: number } = {},
): Promise<void> {
  const timeout = opts.timeout ?? 30000;
  const loc = page.getByText(text, { exact: false }).first();
  await expect(loc).toBeHidden({ timeout }).catch(async () => {
    await expect(loc).toHaveCount(0, { timeout: 1000 });
  });
}

/**
 * Retry an async assertion until it passes (Playwright `toPass`).
 * Use for status badges and other eventually-consistent UI.
 */
export async function eventually(
  fn: () => Promise<void>,
  opts: { timeout?: number; intervals?: number[] } = {},
): Promise<void> {
  await expect(fn).toPass({
    timeout: opts.timeout ?? 30000,
    intervals: opts.intervals ?? [250, 500, 1000],
  });
}
