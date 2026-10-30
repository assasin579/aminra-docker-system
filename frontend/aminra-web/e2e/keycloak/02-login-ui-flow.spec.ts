/**
 * Tier 1 Playwright E2E — normal-user login UI contract.
 *
 * Current product decision: normal business/provider login pages keep the
 * AMINRA-owned fallback form, but when NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED=true
 * they must also expose the Keycloak SSO entry point. This catches the Next.js
 * build-time env drift class where runtime env is correct but the browser bundle
 * still behaves as if Keycloak is disabled.
 */

import { test, expect } from "./helpers/fixtures";

const FE_URL = process.env.PW_BASE_URL ?? "http://localhost:3100";

function expectedCallbackUrl(): string {
  return encodeURIComponent(`${new URL(FE_URL).origin}/auth/callback`);
}

async function expectVisibleKeycloakSso(page: any) {
  await expect(page.getByTestId("keycloak-sso-button")).toBeVisible();
  await expect(page.getByTestId("keycloak-account-cta")).toHaveCount(0);
  await expect(page.getByText(/Keycloak/i)).toBeVisible();
}

test.describe("Business login page UI", () => {
  test("renders AMINRA-owned form fields", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /^Đăng nhập$/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Về trang chủ/i })).toHaveAttribute("href", "/landing");
    await expectVisibleKeycloakSso(page);
  });

  test("Keycloak CTA starts OIDC redirect", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await page.waitForLoadState("networkidle");
    const ssoButton = page.getByTestId("keycloak-sso-button");
    await expect(ssoButton).toBeEnabled();
    await Promise.all([
      page.waitForURL(/\/realms\/aminra\//, { timeout: 15000 }),
      ssoButton.click(),
    ]);
    expect(page.url()).toContain("client_id=aminra-frontend");
    expect(page.url()).toContain(`redirect_uri=${expectedCallbackUrl()}`);
  });

  test("forgot password link routes to AMINRA reset request page", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    const href = await page.getByRole("link", { name: /Quên mật khẩu/i }).getAttribute("href");
    expect(href).toBe("/forgot-password");
  });
});

test.describe("Provider login page UI", () => {
  test("renders AMINRA-owned provider form with visible Keycloak SSO", async ({ page }) => {
    await page.goto(`${FE_URL}/provider/login`);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByText(/AMINRA xét duyệt/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "Về trang chủ" })).toHaveAttribute(
      "href",
      "/landing",
    );
    await expectVisibleKeycloakSso(page);
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
