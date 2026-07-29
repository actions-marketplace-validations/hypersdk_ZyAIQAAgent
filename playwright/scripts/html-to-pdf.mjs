#!/usr/bin/env node
// Copyright 2026 ZyvorAI Labs Private Limited
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/** Convert a local HTML file to PDF using Playwright (Chromium print). */
import { chromium } from "@playwright/test";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [, , htmlArg, pdfArg] = process.argv;

if (!htmlArg || !pdfArg) {
  console.error("Usage: node html-to-pdf.mjs <input.html> <output.pdf>");
  process.exit(1);
}

const htmlPath = path.resolve(htmlArg);
const pdfPath = path.resolve(pdfArg);

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
  await page.pdf({
    path: pdfPath,
    format: "A4",
    printBackground: true,
    margin: { top: "20mm", bottom: "20mm", left: "15mm", right: "15mm" },
  });
  console.log(`PDF written to ${pdfPath}`);
} finally {
  await browser.close();
}
