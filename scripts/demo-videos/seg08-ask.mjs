import { openLoggedIn, closeAndSave } from "./lib.mjs";

const { browser, context, page } = await openLoggedIn("raw/seg08-ask");
await page.waitForTimeout(4500);

const question = page.locator('button:has-text("How do I migrate a VMware VM to KubeVirt with HyperSDK?")').first();
await question.scrollIntoViewIfNeeded({ timeout: 10000 }).catch(async () => {
  await page.mouse.wheel(0, 5500);
});
await page.waitForTimeout(1500);
await question.click({ timeout: 5000 }).catch(() => {});

// Give the streamed, citation-first answer time to render
await page.waitForTimeout(8000);
await page.mouse.wheel(0, 200);
await page.waitForTimeout(3000);

await closeAndSave(browser, context);
console.log("seg08-ask done");
