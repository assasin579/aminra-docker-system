/**
 * Admin user-edit modal UX regression gate.
 *
 * Issues fixed 2026-04-26 in AdminUserManager.tsx:
 *   1. Password placeholder said "8 ký tự" while BE rule is 10+ upper+lower+digit
 *   2. err.detail (FastAPI 422 array) printed as "[object Object]"
 *   3. Email field hidden on edit — admin couldn't see who they edit if title cropped
 *   4. No ESC / backdrop close
 *   5. No focus management on open
 *   6. No warning when changing role (data-integrity risk)
 *   7. Pending status shown for business (only providers go pending)
 *   8. Save button gray-on-gray when disabled (low contrast)
 *
 * Static guards check the source so future regressions get caught.
 */
import { test, expect } from "@playwright/test";

test.describe("admin user edit UX", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "static guards only need desktop coverage",
    );
  });

  test("AdminUserManager imports parseApiError + validatePassword", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("components/AdminUserManager.tsx", "utf8");
    expect(src, "must use parseApiError for FastAPI 422 unwrapping").toContain(
      "parseApiError",
    );
    expect(
      src,
      "must use validatePassword for client-side rule check",
    ).toContain("validatePassword");
  });

  test("modal supports ESC + backdrop close + focus first input", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("components/AdminUserManager.tsx", "utf8");

    // ESC key handler
    expect(src).toMatch(/key === ['"]Escape['"]/);
    // Backdrop click closes
    expect(src).toMatch(/onClick=\{[^}]*setModal\(null\)/);
    // First input ref + focus
    expect(src).toContain("firstInputRef");
    expect(src).toContain("firstInputRef.current?.focus");
    // Stop propagation on inner content
    expect(src).toMatch(/stopPropagation/);
  });

  test("password placeholder + helper text match BE rule (10+ chars upper/lower/digit)", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("components/AdminUserManager.tsx", "utf8");
    expect(src, "old '8 ký tự' must be replaced").not.toMatch(
      /Tối thiểu 8 ký tự/,
    );
    expect(src, "must explain 10+ chars rule to admin").toMatch(/10\+ ký tự/);
    expect(src, "must mention upper/lower/digit").toMatch(
      /chữ hoa.*chữ thường.*số/i,
    );
  });

  test("edit mode shows email as read-only field (not just title)", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("components/AdminUserManager.tsx", "utf8");
    // The edit branch must render an email input with `readOnly` and `disabled`
    expect(src).toMatch(/value=\{editTarget\?\.email \?\? ["']{2}\}/);
    expect(src).toMatch(/readOnly/);
  });

  test("role-change confirm + 'Pending' status hidden for business", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("components/AdminUserManager.tsx", "utf8");
    // Role-change warning
    expect(src).toMatch(/Đổi vai trò.*có thể gây không nhất quán/);
    // Pending only when role=provider
    expect(src).toMatch(
      /form\.role === ['"]provider['"][^<]*<option value=['"]pending['"]/s,
    );
  });

  test("save button uses navy disabled bg (not gray-on-gray)", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("components/AdminUserManager.tsx", "utf8");
    // Saving state: navy translucent — not the old #E2E8F0 with #5B6B7D text
    expect(src).toMatch(/rgba\((10,31,68|15,44,74),0\.4\)/);
    expect(src, "old gray disabled state must be removed").not.toMatch(
      /saving \? '#E2E8F0' : '#0F2C4A'/,
    );
  });
});
