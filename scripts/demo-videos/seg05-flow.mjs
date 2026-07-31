import { openLoggedIn, closeAndSave } from "./lib.mjs";

const { browser, context, page } = await openLoggedIn("raw/seg05-flow");
await page.waitForTimeout(4500);

const resultHeading = page.locator("text=Flow test result").first();
await resultHeading.scrollIntoViewIfNeeded({ timeout: 10000 }).catch(async () => {
  // fall back: scroll roughly to where the flow section lives
  await page.mouse.wheel(0, 6000);
});
await page.waitForTimeout(2000);

// Try to play the embedded result video
const video = page.locator("video").first();
const hasVideo = await video.count().then((c) => c > 0).catch(() => false);
if (hasVideo) {
  await video.click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(3500);
}

// Scroll down into the step-by-step table
await page.mouse.wheel(0, 400);
await page.waitForTimeout(3000);
await page.mouse.wheel(0, 300);
await page.waitForTimeout(2500);

await closeAndSave(browser, context);
console.log("seg05-flow done");
