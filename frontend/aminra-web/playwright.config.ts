import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config — multi-browser + viewport coverage.
 *
 * Project naming convention: `<browser>-<viewport>` so the matrix is
 * inspectable from `--project=<name>` flag. Visual regression specs target
 * `desktop-chromium` only (single source of truth for snapshots).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: { maxDiffPixels: 200 },
  },
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  use: {
    baseURL:    process.env.PW_BASE_URL ?? "http://localhost:3100",
    trace:      "on-first-retry",
    screenshot: "only-on-failure",
    video:      "retain-on-failure",
    actionTimeout: 10_000,
  },
  projects: [
    // Desktop — primary visual + a11y baseline
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    // Cross-browser parity
    {
      name: "desktop-firefox",
      use: { ...devices["Desktop Firefox"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "desktop-webkit",
      use: { ...devices["Desktop Safari"], viewport: { width: 1440, height: 900 } },
    },
    // Mobile + tablet
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 7"] },
    },
    {
      name: "mobile-safari",
      use: { ...devices["iPhone 14"] },
    },
    {
      name: "tablet",
      use: { ...devices["iPad Pro 11"] },
    },
  ],
});
