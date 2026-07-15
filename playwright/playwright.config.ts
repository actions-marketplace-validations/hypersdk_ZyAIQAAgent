import { defineConfig, devices } from '@playwright/test';
import path from 'path';

const baseURL = process.env.ZYVOR_BASE_URL || 'https://zyvor.dev';
const repoRoot = path.resolve(__dirname, '..');
const multiBrowser = process.env.ENABLE_MULTI_BROWSER === 'true';
const regressionMode = process.env.ENABLE_REGRESSION === 'true';
// Chromium refuses to sandbox as root (containers) — set in docker/Dockerfile
const noSandbox = process.env.ZYVOR_NO_SANDBOX === 'true';

const projects = [
  {
    name: 'chromium',
    use: { ...devices['Desktop Chrome'] },
  },
];

if (multiBrowser) {
  projects.push(
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  );
}

export default defineConfig({
  testDir: path.join(repoRoot, 'tests'),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI
    ? 1
    : process.env.ZYVOR_PW_WORKERS
      ? parseInt(process.env.ZYVOR_PW_WORKERS, 10)
      : undefined,
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(repoRoot, 'reports'), open: 'never' }],
    ['json', { outputFile: path.join(repoRoot, 'reports', 'results.json') }],
  ],
  use: {
    baseURL,
    // Self-signed / invalid TLS on the target under test
    ignoreHTTPSErrors: process.env.ZYVOR_IGNORE_HTTPS_ERRORS === 'true',
    trace: 'retain-on-failure',
    screenshot: regressionMode ? 'on' : 'only-on-failure',
    video: {
      // 'on' records every test (dashboard jobs set ZYVOR_VIDEO=on)
      mode: process.env.ZYVOR_VIDEO === 'on' ? 'on' : 'retain-on-failure',
      size: { width: 1280, height: 720 },
    },
    actionTimeout: 15000,
    navigationTimeout: 30000,
    launchOptions: noSandbox ? { args: ['--no-sandbox'] } : {},
  },
  outputDir: path.join(repoRoot, 'test-results'),
  preserveOutput: 'always',
  projects,
});
