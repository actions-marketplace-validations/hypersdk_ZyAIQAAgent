import { openLoggedIn, closeAndSave } from "./lib.mjs";

const { browser, context, page } = await openLoggedIn("raw/seg04-smoke");
await page.waitForTimeout(4500);

const smokeBtn = page.locator('button:has-text("Smoke")').first();
await smokeBtn.scrollIntoViewIfNeeded();
await page.waitForTimeout(1500);
await smokeBtn.click();

// Poll until the run finishes (Stop button disappears), capped at ~3 min
const t0 = Date.now();
for (let i = 0; i < 95; i++) {
  await page.waitForTimeout(2000);
  const text = await page.evaluate(() => document.body.innerText);
  if (!text.includes("⏹ Stop") && i > 2) break;
  if ((Date.now() - t0) / 1000 > 170) break;
}
await page.waitForTimeout(2500);

await closeAndSave(browser, context);
console.log("seg04-smoke done", ((Date.now() - t0) / 1000).toFixed(0), "s");
