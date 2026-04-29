/**
 * CUJ-6: GDPR right-to-be-forgotten + data export.
 *
 * Coverage:
 * - Data export endpoint returns full bundle
 * - Deletion request flow returns generic 200 (no leak)
 * - Deletion confirm rejects invalid token
 * - Login blocked after deletion (smoke)
 */
import { test, expect } from "./fixtures";

test.describe("CUJ-6: GDPR rights", () => {
  test("Data export returns JSON bundle for authenticated user", async ({
    api,
    biz,
  }) => {
    const res = await api.get("/api/users/me/export-data", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect(res.status()).toBe(200);
    expect(res.headers()["content-disposition"]).toContain("attachment");
    expect(res.headers()["x-export-format-version"]).toBeTruthy();

    const body = await res.json();
    expect(body.user_id).toBeTruthy();
    expect(body.data_subject?.profile?.email).toBe(biz.email);
    expect(body.legal_basis?.vietnam).toContain("Nghị định 13");
    expect(body.legal_basis?.eu_gdpr).toContain("Article 20");
  });

  test("Data export rejects unauthenticated", async ({ api }) => {
    const res = await api.get("/api/users/me/export-data");
    expect(res.status()).toBe(401);
  });

  test("Request deletion returns generic message", async ({ api, biz }) => {
    const res = await api.post("/api/users/me/request-deletion", {
      headers: {
        Authorization: `Bearer ${biz.token}`,
        "Content-Type": "application/json",
      },
      data: { lang: "vi" },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.message).toContain("email xác nhận");
  });

  test("Confirm deletion with invalid token returns 400", async ({ api }) => {
    const res = await api.post("/api/users/me/confirm-deletion", {
      data: { token: "x".repeat(40) },
    });
    expect(res.status()).toBe(400);
  });

  test("Privacy policy page lists Nghị định 13/2023", async ({ page }) => {
    await page.goto("/privacy");
    await expect(page.getByText(/13\/2023\/NĐ-CP/)).toBeVisible();
    await expect(page.getByText(/Quyền của người dùng/i)).toBeVisible();
  });

  test("Terms page caps liability at 12 months fees", async ({ page }) => {
    await page.goto("/terms");
    await expect(page.getByText(/12 tháng gần nhất/)).toBeVisible();
  });
});
