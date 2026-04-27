/**
 * RevisionPanel visibility behavior.
 *
 * Issue 2026-04-26: provider opens a submission with status `pending` /
 * `assigned` / `approved` and sees a static "Yêu cầu sửa hồ sơ" block with
 * empty history — looks broken.
 *
 * Fix: panel hides itself entirely when no form is actionable AND no history
 * exists. Shows contextual hint only when there's a clear next-step.
 */
import { test, expect } from "@playwright/test";

test.describe("revision panel visibility logic", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "static guard only needs desktop coverage",
    );
  });

  test("source: panel returns null when no action + no history", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("components/submissions/RevisionPanel.tsx", "utf8");

    // Helper booleans for clarity in source
    expect(src).toContain("providerCanRequest");
    expect(src).toContain("businessCanResubmit");
    expect(src).toContain("hasAction");
    expect(src).toContain("hasHistory");

    // Early return when nothing to show
    expect(src, "must hide entire panel on dead states").toMatch(
      /if \(!loading && !hasAction && !hasHistory\) \{[\s\S]*?return null;[\s\S]*?\}/,
    );

    // Contextual hint for provider on pending/assigned status (rare but informative)
    expect(src).toMatch(/status === ['"]pending['"] \|\| status === ['"]assigned['"]/);
  });

  test("source: form conditions still align with backend ALLOWED_FROM_STATUSES", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("components/submissions/RevisionPanel.tsx", "utf8");
    // Backend allows revision FROM reviewing|returned. FE must not trigger 4xx
    // by submitting from other states — these are the only statuses that show
    // the form.
    expect(src).toMatch(/role === ['"]provider['"] && \(status === ['"]reviewing['"] \|\| status === ['"]returned['"]\)/);
    expect(src).toMatch(/role === ['"]business['"] && status === ['"]revision_required['"]/);
  });
});
