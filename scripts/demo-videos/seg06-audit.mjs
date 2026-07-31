import { openLoggedIn, closeAndSave } from "./lib.mjs";

const { browser, context, page } = await openLoggedIn("raw/seg06-audit");
await page.waitForTimeout(4500);

const urlInput = page.locator('input[placeholder="https://your-app.example.com"]').first();
await urlInput.scrollIntoViewIfNeeded();
await page.waitForTimeout(1000);
await urlInput.click();
await urlInput.type("https://zyvor.dev", { delay: 60 });
await page.waitForTimeout(800);

await page.click('button:has-text("Run audit")');

const t0 = Date.now();
for (let i = 0; i < 30; i++) {
  await page.waitForTimeout(1500);
  const text = await page.evaluate(() => document.body.innerText);
  if (!text.includes("⏹ Stop") && i > 1) break;
  if ((Date.now() - t0) / 1000 > 45) break;
}
await page.waitForTimeout(3000);

await closeAndSave(browser, context);
console.log("seg06-audit done");
