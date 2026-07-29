import { test, expect } from '../../playwright/fixtures/base';
import { waitForPageReady } from '../../playwright/utils/helpers';
import { screenshotOptions } from '../../playwright/utils/visual';
import { captureBaseline } from '../../playwright/utils/api';

test.describe('Visual Regression', () => {
  test('homepage visual baseline', { tag: ['@visual', '@smoke'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();

    const opts = await screenshotOptions(page);
    await expect(page).toHaveScreenshot('homepage-hero.png', opts);

    // Optional: also feed the Pillow/Rust post-run pipeline when ENABLE_REGRESSION=true
    if (process.env.ENABLE_REGRESSION === 'true') {
      await captureBaseline(page, 'homepage-hero');
    }
  });

  test('products section visual baseline', { tag: ['@visual'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);

    const section = page.getByText(/14.*products|All 14|product suite/i).first();
    await section.scrollIntoViewIfNeeded();
    await expect(section).toBeAttached();

    const opts = await screenshotOptions(page);
    await expect(section).toHaveScreenshot('products-section.png', opts);

    if (process.env.ENABLE_REGRESSION === 'true') {
      await captureBaseline(page, 'products-section');
    }
  });
});
