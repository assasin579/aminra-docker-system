/**
 * Layer 2 — Visual regression.
 *
 * Pixel-diff snapshot of stable public pages. Run on `desktop-chromium` only
 * to keep snapshot count manageable (one source of truth per page).
 *
 * On first run: snapshots saved to e2e/visual-regression.spec.ts-snapshots/
 * On subsequent runs: diff against baseline. CI fails if maxDiffPixels exceeded.
 *
 * To update baselines after intentional changes:
 *     npx playwright test e2e/visual-regression.spec.ts --update-snapshots
 */
import { test, expect } from "@playwright/test";

// Visual regression only on chromium-desktop — single source of truth
test.beforeEach(({}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop-chromium",
    "visual baseline only on desktop-chromium",
  );
});

const PUBLIC_VISUAL_PAGES = [
  { path: "/", name: "landing" },
  { path: "/business/login", name: "business-login" },
  { path: "/provider/login", name: "provider-login" },
  { path: "/forgot-password", name: "forgot-password" },
  { path: "/privacy", name: "privacy" },
  { path: "/terms", name: "terms" },
];

test.describe("Layer 2 — Visual regression (public pages)", () => {
  for (const { path, name } of PUBLIC_VISUAL_PAGES) {
    test(`${name} matches baseline`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      // Hide elements that change between runs (timestamps, animations)
      await page.addStyleTag({
        content: `
          * { animation: none !important; transition: none !important; }
          [suppressHydrationWarning], time, [data-dynamic] { visibility: hidden; }
        `,
      });
      await expect(page).toHaveScreenshot(`${name}.png`, {
        fullPage: true,
        animations: "disabled",
      });
    });
  }

  test("verify page — 404 state", async ({ page }) => {
    await page.goto("/verify/HALAL-NOT-EXIST");
    await page.waitForLoadState("networkidle");
    await page.addStyleTag({
      content: `* { animation: none !important; transition: none !important; }`,
    });
    await expect(page).toHaveScreenshot("verify-404.png", {
      fullPage: true,
      animations: "disabled",
    });
  });
});
