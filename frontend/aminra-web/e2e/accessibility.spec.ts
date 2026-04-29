/**
 * Layer 3 — Accessibility (axe-core).
 *
 * WCAG 2.1 AA compliance check on all PUBLIC pages.
 *
 * Strategy:
 * - Baseline gate: ZERO `critical` violations (test FAILS if any).
 * - `serious` (color contrast etc.) tracked + logged but tolerated until
 *   design refresh — flip to gate=zero before EU CSRD audit.
 */
import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

const PUBLIC_PAGES = [
  { path: "/", name: "landing" },
  { path: "/business/login", name: "business-login" },
  { path: "/provider/login", name: "provider-login" },
  { path: "/forgot-password", name: "forgot-password" },
  { path: "/privacy", name: "privacy" },
  { path: "/terms", name: "terms" },
];

const VERIFY_PATH = "/verify/HALAL-2026-NOTREAL"; // 404 state

test.describe("Layer 3 — Accessibility (public pages)", () => {
  for (const { path, name } of PUBLIC_PAGES) {
    test(`${name} — no critical a11y violations`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();

      const summary = results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.length,
        help: v.help,
      }));
      if (summary.length > 0) {
        console.log(
          `[a11y:${name}] ${summary.length} violations:`,
          JSON.stringify(summary, null, 2),
        );
      }

      const critical = results.violations.filter(
        (v) => v.impact === "critical",
      );
      expect(critical, `Critical a11y violations on ${name}`).toEqual([]);
    });
  }

  test("verify page (404 state) — no critical a11y violations", async ({
    page,
  }) => {
    await page.goto(VERIFY_PATH);
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(results.violations.filter((v) => v.impact === "critical")).toEqual(
      [],
    );
  });
});
