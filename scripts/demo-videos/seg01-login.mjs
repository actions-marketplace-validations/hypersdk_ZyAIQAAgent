import { chromium } from "playwright";
import { BASE, USER, PASS } from "./lib.mjs";

const browser = await chromium.launch({ channel: "chrome" });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: "raw/seg01-login", size: { width: 1920, height: 1080 } },
});
const page = await context.newPage();

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await page.locator('input[name="username"]').click();
await page.locator('input[name="username"]').type(USER, { delay: 90 });
await page.waitForTimeout(300);
await page.locator('input[name="password"]').click();
await page.locator('input[name="password"]').type(PASS, { delay: 90 });
await page.waitForTimeout(500);
await page.click('button[type="submit"]');
await page.waitForURL((u) => u.pathname.startsWith("/dashboard"), { timeout: 15000 }).catch(() => {});
await page.waitForTimeout(4500); // boot splash + settle

await page.close();
await context.close();
await browser.close();
console.log("seg01-login done");
