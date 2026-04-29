/**
 * Phase 1 Batch 5 — State machine matrix + scoring math (2026-04-26)
 *
 * Covers fixes from the bug audit:
 *   W3-M2  full 49-cell transition matrix enforced via `_validate_transition`
 *   W3-M3  save_evaluation auto-promotes only from {pending, assigned} → reviewing
 *   W3-M11 business_score restricts doc_score to docs in this provider's submissions
 *   W3-M12 business_score audit_score uses only completed/report_submitted visits
 */
import { test, expect } from "@playwright/test";

test.describe("Phase 1 Batch 5 — state + scoring", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "integration tests only need desktop coverage",
    );
  });

  test("static guards — code reflects all batch 5 fixes", async () => {
    const { readFile } = await import("node:fs/promises");
    const sub = await readFile(
      "../../backend/auth/submission_router.py",
      "utf8",
    );
    const aud = await readFile("../../backend/auth/audit_router.py", "utf8");

    // W3-M2: matrix exists with all 7 statuses
    expect(sub).toMatch(/_ALLOWED_TRANSITIONS\s*=\s*\{/);
    for (const status of [
      "pending",
      "assigned",
      "reviewing",
      "revision_required",
      "returned",
      "rejected",
      "approved",
    ]) {
      expect(sub).toMatch(new RegExp(`["']${status}["']`));
    }
    // W3-M2: helper raises 409 on invalid transitions
    expect(sub).toMatch(/_validate_transition\(/);
    expect(sub).toMatch(/Chuyển trạng thái không hợp lệ/);
    // W3-M2: terminal states have no outgoing transitions
    expect(sub).toMatch(/["']rejected["']:\s*set\(\),\s*#\s*terminal/);
    expect(sub).toMatch(/["']approved["']:\s*set\(\),\s*#\s*terminal/);

    // W3-M3: save_evaluation calls _validate_transition before auto-promotion
    expect(sub).toMatch(
      /_validate_transition\(sub_info\["status"\],\s*["']reviewing["']\)/,
    );

    // W3-M2: approve-final guards transition before flipping
    expect(sub).toMatch(
      /_validate_transition\(sub\["status"\],\s*["']approved["']\)/,
    );

    // W3-M11: doc_score CTE filters via provider_doc_ids
    expect(aud).toMatch(/provider_doc_ids/);
    expect(aud).toMatch(/JOIN provider_doc_ids/);

    // W3-M12: audit_score uses FILTER on completed/report_submitted
    expect(aud).toMatch(
      /AVG\(compliance_score\) FILTER \(\s*WHERE status IN \(['"]completed['"], ['"]report_submitted['"]\)/,
    );
  });

  test("transition matrix is sane: terminal states cannot transition out", async () => {
    // Re-derive the matrix structurally to catch typos in the python dict.
    const { readFile } = await import("node:fs/promises");
    const sub = await readFile(
      "../../backend/auth/submission_router.py",
      "utf8",
    );

    // rejected and approved must map to set() (empty, terminal)
    expect(sub).toMatch(/["']rejected["']:\s*set\(\)/);
    expect(sub).toMatch(/["']approved["']:\s*set\(\)/);

    // revision_required only allows reviewing
    expect(sub).toMatch(
      /["']revision_required["']:\s*\{\s*["']reviewing["']\s*\}/,
    );
  });
});
