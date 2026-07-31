import { openLoggedIn, closeAndSave } from "./lib.mjs";

const { browser, context, page } = await openLoggedIn("raw/seg07-probes");
await page.waitForTimeout(4500);

const headersBtn = page.locator('button:has-text("Headers")').first();
await headersBtn.scrollIntoViewIfNeeded();
await page.waitForTimeout(1500);

// Fill the nearest "https://…" URL input above the probes row, if present
const probeUrlInput = page.locator('input[placeholder="https://…"]').first();
const hasInput = await probeUrlInput.count().then((c) => c > 0).catch(() => false);
if (hasInput) {
  await probeUrlInput.click();
  await probeUrlInput.type("https://zyvor.dev", { delay: 50 });
  await page.waitForTimeout(600);
}

for (const label of ["Headers", "Cookies", "CORS"]) {
  const btn = page.locator(`button:has-text("${label}")`).first();
  await btn.click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(2500);
}

await page.waitForTimeout(2000);
await closeAndSave(browser, context);
console.log("seg07-probes done");
