import { openLoggedIn, closeAndSave } from "./lib.mjs";

const { browser, context, page } = await openLoggedIn("raw/seg03-actions");
await page.waitForTimeout(4500);

// Scroll to the Actions panel and slowly pan through the cards
await page.locator('button:has-text("Smoke")').first().scrollIntoViewIfNeeded();
await page.waitForTimeout(2000);

for (let i = 0; i < 6; i++) {
  await page.mouse.wheel(0, 300);
  await page.waitForTimeout(1400);
}

await closeAndSave(browser, context);
console.log("seg03-actions done");
