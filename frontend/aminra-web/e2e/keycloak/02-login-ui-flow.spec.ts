/**
 * Tier 1 Playwright E2E — normal-user login UI contract.
 *
 * Current product decision: normal business/provider users stay on AMINRA-owned
 * credential pages. Keycloak remains the identity backend and direct-grant token
 * issuer for tests/admin flows, but public login/register/reset screens must not
 * expose visible Keycloak SSO buttons or redirect normal users away from AMINRA.
 */

import { test, expect } from "./helpers/fixtures";

const FE_URL = process.env.PW_BASE_URL ?? "http://localhost:3100";

async function expectNoVisibleKeycloakSso(page: any) {
  await expect(page.getByTestId("keycloak-sso-button")).toHaveCount(0);
  await expect(page.getByTestId("keycloak-account-cta")).toHaveCount(0);
  await expect(page.getByText(/Keycloak|SSO|di trú|TOTP/i)).toHaveCount(0);
}

test.describe("Business login page UI", () => {
  test("renders AMINRA-owned form fields", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /^Đăng nhập$/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Về trang chủ/i })).toHaveAttribute("href", "/landing");
    await expectNoVisibleKeycloakSso(page);
  });

  test("forgot password link routes to AMINRA reset request page", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    const href = await page.getByRole("link", { name: /Quên mật khẩu/i }).getAttribute("href");
    expect(href).toBe("/forgot-password");
  });
});

test.describe("Provider login page UI", () => {
  test("renders AMINRA-owned provider form without visible Keycloak SSO", async ({ page }) => {
    await page.goto(`${FE_URL}/provider/login`);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByText(/AMINRA xét duyệt/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "Về trang chủ" })).toHaveAttribute(
      "href",
      "/landing",
    );
    await expectNoVisibleKeycloakSso(page);
  });
});

test.describe("Password reset pages", () => {
  test.skip("email-reset flow is SMTP-dependent and intentionally deferred", async () => {});
});

test.describe("OIDC callback page", () => {
  test("direct visit without code shows error fallback or exits callback", async ({ page }) => {
    await page.goto(`${FE_URL}/auth/callback`);
    const errorOrRedirect = await page
      .waitForFunction(
        () => document.body.innerText.includes("thất bại") || window.location.pathname !== "/auth/callback",
        { timeout: 5000 },
      )
      .catch(() => null);
    expect(errorOrRedirect).toBeTruthy();
  });

  test("callback with invalid code shows error", async ({ page }) => {
    await page.goto(`${FE_URL}/auth/callback?code=invalid-code-xyz&state=invalid`);
    await page.waitForTimeout(2000);
    const hasError = await page
      .getByText(/thất bại|từ chối|lỗi/i)
      .isVisible()
      .catch(() => false);
    expect(hasError).toBeTruthy();
  });
});
