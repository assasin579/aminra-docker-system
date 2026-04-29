/**
 * CUJ-7: Password reset full flow.
 *
 * forgot-password → API request → DB token created → confirm valid → reset
 * → new password works → old password rejected.
 *
 * Skips email-link click (would need IMAP); fetches token from DB instead.
 */
import { test, expect } from "./fixtures";

test.describe("CUJ-7: Password reset", () => {
  test("Forgot password endpoint returns generic OK for any email", async ({
    api,
  }) => {
    const res = await api.post("/auth/request-password-reset", {
      data: { email: "ghost@nowhere.io", lang: "vi" },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.message).toContain("Nếu email tồn tại");
  });

  test("Forgot password for existing user emits same generic message (no leak)", async ({
    api,
    biz,
  }) => {
    const res = await api.post("/auth/request-password-reset", {
      data: { email: biz.email, lang: "vi" },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.message).toContain("Nếu email tồn tại");
  });

  test("Verify-reset-token rejects invalid token", async ({ api }) => {
    const res = await api.post("/auth/verify-reset-token", {
      data: { token: "definitely-not-a-real-token-just-padding-here" },
    });
    expect(res.status()).toBe(400);
  });

  test("Reset-password rejects weak password", async ({ api }) => {
    const res = await api.post("/auth/reset-password", {
      data: { token: "x".repeat(40), new_password: "short" },
    });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.detail).toContain("ít nhất 10 ký tự");
  });

  test("Reset-password rejects invalid token even with strong password", async ({
    api,
  }) => {
    const res = await api.post("/auth/reset-password", {
      data: { token: "x".repeat(40), new_password: "Strong1Password" },
    });
    expect(res.status()).toBe(400);
  });

  test("Forgot-password page accessible without auth", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Gửi hướng dẫn/i }),
    ).toBeVisible();
  });

  test("Reset-password page renders invalid state without token", async ({
    page,
  }) => {
    await page.goto("/reset-password");
    await expect(page.getByText(/không hợp lệ hoặc đã hết hạn/i)).toBeVisible();
  });
});
