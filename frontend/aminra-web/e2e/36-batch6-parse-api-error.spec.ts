/**
 * Phase 1 Batch 6 — UX cleanup (2026-04-26)
 *
 * Covers parseApiError migration. The bug: many callsites used the naive
 * `throw new Error(err.detail || 'fallback')` pattern which crashes to
 * `[object Object]` when FastAPI returns a 422 validation array. The fix
 * is to centralize parsing through `lib/apiError.ts::parseApiError`.
 */
import { test, expect } from "@playwright/test";

const MIGRATED_FILES = [
  "app/members/page.tsx",
  "app/auditors/page.tsx",
  "app/audits/page.tsx",
  "app/audits/templates/page.tsx",
  "app/self-assessment/page.tsx",
  "app/submissions/page.tsx",
  "components/AdminAuthContext.tsx",
  "components/AdminPage.tsx",
];

test.describe("Phase 1 Batch 6 — UX cleanup", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "static guards only need desktop coverage",
    );
  });

  for (const path of MIGRATED_FILES) {
    test(`parseApiError used in ${path}`, async () => {
      const { readFile } = await import("node:fs/promises");
      const src = await readFile(`../../frontend/aminra-web/${path}`, "utf8");
      expect(src, `${path} must import parseApiError`).toContain("from '@/lib/apiError'");
      expect(src, `${path} must call parseApiError`).toContain("parseApiError(");
      // No naive `err.detail ||` left after migration
      expect(src, `${path} must NOT use raw err.detail || pattern`).not.toMatch(/err\.detail\s*\|\|/);
    });
  }
});
