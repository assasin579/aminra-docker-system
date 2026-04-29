/**
 * Admin auth unification (Option 2):
 * Verify that after logging in via the legacy /admin flow (opaque token in
 * `aminra_admin_token`), the analytics + audit-logs + overdue-submissions
 * pages can call their /api/auth/admin/* endpoints successfully.
 *
 * This is the regression gate for the bug where these 3 pages only read
 * `aminra_user_token`, leaving an admin who logged in via /admin stranded.
 */
import { test, expect } from "@playwright/test";

const ADMIN_USERNAME = "admin";
const ADMIN_PASSWORD = "aminra2026";

test.describe("admin unified auth", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "admin auth test only runs on desktop projects",
    );
  });

  test("legacy /admin token unlocks analytics + audit-logs + overdue", async ({
    page,
    request,
  }) => {
    const loginRes = await request.post("/api/admin/login", {
      data: { username: ADMIN_USERNAME, password: ADMIN_PASSWORD },
    });
    expect(loginRes.ok()).toBeTruthy();
    const { token } = await loginRes.json();
    expect(token).toBeTruthy();

    await page.addInitScript((t) => {
      localStorage.setItem("aminra_admin_token", t);
      localStorage.removeItem("aminra_user_token");
    }, token);

    await page.goto("/admin/analytics");
    await expect(
      page.getByRole("heading", { name: "Analytics dashboard" }),
    ).toBeVisible();
    await expect(page.getByText(/Cập nhật:/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Cần đăng nhập admin")).toHaveCount(0);

    await page.goto("/admin/audit-logs");
    await expect(
      page.getByText(/Audit logs|Nhật ký|audit/i).first(),
    ).toBeVisible();
    await expect(page.getByText("Cần đăng nhập admin")).toHaveCount(0);

    await page.goto("/admin/overdue-submissions");
    await expect(page.getByText("Cần đăng nhập admin")).toHaveCount(0);
  });

  test("non-admin JWT is rejected by admin endpoints (regression)", async ({
    request,
  }) => {
    const r = await request.post("/api/auth/login", {
      data: {
        email: "cb-demo@demo.aminra.vn",
        password: "DemoP@ss2026",
        role: "provider",
      },
    });
    if (!r.ok())
      test.skip(
        true,
        "demo provider not seeded; skipping non-admin regression",
      );
    const { access_token } = await r.json();

    const an = await request.get("/api/auth/admin/analytics", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(an.status()).toBe(403);
  });
});
