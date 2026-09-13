/**
 * Admin auth unification (Option 2):
 * Verify that after storing a Keycloak platform_admin token in
 * `aminra_user_token`, the analytics + audit-logs + overdue-submissions pages
 * can call their /api/auth/admin/* endpoints successfully.
 *
 * This is the regression gate for the bug where these 3 pages only read
 * the frontend accidentally looked for the retired opaque admin session.
 */
import { test, expect } from "@playwright/test";
import { requireAdminToken } from "./helpers/admin-token";
import { requireKeycloakUserToken } from "./helpers/auth-token";

test.describe("admin unified auth", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "admin auth test only runs on desktop projects",
    );
  });

  test("Keycloak platform_admin token unlocks analytics + audit-logs + overdue", async ({
    page,
    request,
  }) => {
    const token = await requireAdminToken(request);

    await page.addInitScript((t) => {
      localStorage.setItem("aminra_user_token", t);
      localStorage.removeItem("aminra_admin_token");
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
    const password = process.env.PW_PROVIDER_PASSWORD ?? process.env.PROVIDER_DEMO_PW ?? process.env.DEMO_PW;
    if (!password) test.skip(true, "provider Keycloak password not configured");
    const access_token = await requireKeycloakUserToken(request, {
      email: process.env.PW_PROVIDER_EMAIL ?? "cb-demo@demo.aminra.vn",
      password: password as string,
    });

    const an = await request.get("/api/auth/admin/analytics", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(an.status()).toBe(403);
  });
});
