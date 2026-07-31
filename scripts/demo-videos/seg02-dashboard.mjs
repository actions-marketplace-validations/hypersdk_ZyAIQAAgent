import { openLoggedIn, closeAndSave } from "./lib.mjs";

const { browser, context, page } = await openLoggedIn("raw/seg02-dashboard");
await page.waitForTimeout(4500); // boot splash

// Status hero
await page.mouse.move(960, 400);
await page.waitForTimeout(2500);

// Scroll to pods, click one to open the log drawer
const podCard = page.locator('[class*="pod" i]').first();
await page.mouse.wheel(0, 500);
await page.waitForTimeout(1500);
const clicked = await podCard.click({ timeout: 5000 }).then(() => true).catch(() => false);
if (clicked) {
  await page.waitForTimeout(3000);
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(1000);
}

// Scroll to workloads/QA runs sparkline area
await page.mouse.wheel(0, 900);
await page.waitForTimeout(3000);

await closeAndSave(browser, context);
console.log("seg02-dashboard done");
