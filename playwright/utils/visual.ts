import type { Locator, Page } from '@playwright/test';

/** Selectors that flake pixel diffs (charts, clocks, skeletons). Shared with route-sweep. */
export const DYNAMIC_MASK_SELECTORS = [
  'canvas',
  'video',
  '[class*="recharts"]',
  'time',
  '[class*="clock"]',
  '[class*="timestamp"]',
  '[class*="skeleton"]',
];

/**
 * Collect locators to mask for `toHaveScreenshot` / route-sweep style diffs.
 */
export async function dynamicMasks(page: Page, maxPerSelector = 20): Promise<Locator[]> {
  const masks: Locator[] = [];
  for (const sel of DYNAMIC_MASK_SELECTORS) {
    const loc = page.locator(sel);
    const n = await loc.count().catch(() => 0);
    for (let i = 0; i < Math.min(n, maxPerSelector); i++) {
      masks.push(loc.nth(i));
    }
  }
  return masks;
}

/** Default options for native Playwright screenshot assertions. */
export async function screenshotOptions(page: Page) {
  return {
    animations: 'disabled' as const,
    mask: await dynamicMasks(page),
  };
}
