import { openLoggedIn, closeAndSave } from "./lib.mjs";

const { browser, context, page } = await openLoggedIn("raw/seg09-noc");
await page.waitForTimeout(4500);
await page.mouse.wheel(0, 0); // ensure we're at the top for the brand + palette

const brand = page.locator("text=MISSION CONTROL").first();
await brand.dblclick({ timeout: 5000 }).catch(() => {});
await page.waitForTimeout(4000);
await page.keyboard.press("Escape").catch(() => {});
await page.waitForTimeout(1200);

await page.keyboard.press("Meta+K").catch(() => {});
await page.waitForTimeout(1000);
await page.keyboard.type("audit", { delay: 90 }).catch(() => {});
await page.waitForTimeout(2500);
await page.keyboard.press("Escape").catch(() => {});
await page.waitForTimeout(1500);

await closeAndSave(browser, context);
console.log("seg09-noc done");
