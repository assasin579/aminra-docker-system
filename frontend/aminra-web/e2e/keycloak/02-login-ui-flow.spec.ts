/**
 * Tier 1 Playwright E2E — Login UI flow (25 tests).
 *
 * Browser-driven scenarios. User clicks SSO button, redirects to
 * Keycloak login page, returns via /auth/callback, lands on dashboard.
 *
 * Tests verify FE rendering + redirect behaviour. Some tests check
 * Keycloak login page content; others check FE error states.
 */

import { test, expect } from "./helpers/fixtures";

const FE_URL = process.env.PW_BASE_URL ?? "http://localhost:3100";

// ── 1. Business login page renders SSO button when flag on ────────────────────

test.describe("Business login page UI", () => {
  test("renders form fields when page loads", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test("renders Keycloak SSO button when flag enabled", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await expect(page.getByTestId("keycloak-sso-button")).toBeVisible();
  });

  test("renders 'HOẶC' divider", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await expect(page.getByText("HOẶC")).toBeVisible();
  });

  test("renders TOTP hint under SSO button", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await expect(page.getByText(/2 yếu tố/i)).toBeVisible();
  });

  test("legacy email+password form remains functional alongside SSO", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await expect(page.getByRole("button", { name: /^Đăng nhập$/ })).toBeVisible();
  });

  test("forgot password link is present", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await expect(page.getByRole("link", { name: /Quên mật khẩu/i })).toBeVisible();
  });
});


// ── 2. Provider login page UI ───────────────────────────────────────────────

test.describe("Provider login page UI", () => {
  test("renders Keycloak SSO button", async ({ page }) => {
    await page.goto(`${FE_URL}/provider/login`);
    await expect(page.getByTestId("keycloak-sso-button")).toBeVisible();
  });

  test("renders auditor-specific TOTP hint", async ({ page }) => {
    await page.goto(`${FE_URL}/provider/login`);
    await expect(page.getByText(/Auditor.*TOTP/i)).toBeVisible();
  });

  test("renders trusted bodies badge", async ({ page }) => {
    await page.goto(`${FE_URL}/provider/login`);
    await expect(page.getByText(/AMINRA xét duyệt/i)).toBeVisible();
  });
});


// ── 3. Forgot/reset password notices ─────────────────────────────────────────

test.describe("Forgot password page", () => {
  test("renders Keycloak SSO notice when flag on", async ({ page }) => {
    await page.goto(`${FE_URL}/forgot-password`);
    await expect(page.getByTestId("keycloak-account-cta")).toBeVisible();
  });

  test("CTA links to Keycloak account console", async ({ page }) => {
    await page.goto(`${FE_URL}/forgot-password`);
    const href = await page.getByTestId("keycloak-account-cta").getAttribute("href");
    expect(href).toContain("/realms/aminra/account");
  });

  test("legacy form still rendered for unmigrated users", async ({ page }) => {
    await page.goto(`${FE_URL}/forgot-password`);
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });
});

test.describe("Reset password page", () => {
  test("renders SSO notice when accessed without token", async ({ page }) => {
    await page.goto(`${FE_URL}/reset-password`);
    await expect(page.getByTestId("keycloak-account-cta")).toBeVisible();
  });

  test("notice mentions migrated accounts", async ({ page }) => {
    await page.goto(`${FE_URL}/reset-password`);
    await expect(page.getByText(/di trú/i)).toBeVisible();
  });
});


// ── 4. SSO redirect flow ─────────────────────────────────────────────────────

test.describe("SSO redirect flow", () => {
  test("clicking SSO button redirects to Keycloak", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra\/protocol\/openid-connect\/auth/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    expect(page.url()).toContain("realms/aminra/protocol/openid-connect/auth");
  });

  test("redirect URL contains response_type=code", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    expect(page.url()).toMatch(/response_type=code/);
  });

  test("redirect URL contains client_id=aminra-frontend", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    expect(page.url()).toContain("client_id=aminra-frontend");
  });

  test("redirect URL contains code_challenge (PKCE)", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    expect(page.url()).toMatch(/code_challenge=/);
  });

  test("redirect URL has code_challenge_method=S256", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    expect(page.url()).toContain("code_challenge_method=S256");
  });

  test("redirect URL has state parameter", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    expect(page.url()).toMatch(/state=/);
  });

  test("redirect URL has redirect_uri pointing to /auth/callback", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    expect(decodeURIComponent(page.url())).toContain("/auth/callback");
  });

  test("Keycloak login page renders username field", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    await expect(page.locator('input[name="username"]')).toBeVisible({ timeout: 10000 });
  });

  test("Keycloak login page renders password field", async ({ page }) => {
    await page.goto(`${FE_URL}/business/login`);
    await Promise.all([
      page.waitForURL(/realms\/aminra/),
      page.getByTestId("keycloak-sso-button").click(),
    ]);
    await expect(page.locator('input[name="password"]')).toBeVisible({ timeout: 10000 });
  });
});


// ── 5. Callback page handling ────────────────────────────────────────────────

test.describe("OIDC callback page", () => {
  test("direct visit without code shows error fallback", async ({ page }) => {
    await page.goto(`${FE_URL}/auth/callback`);
    // Either error message or redirect
    const errorOrRedirect = await page.waitForFunction(
      () => document.body.innerText.includes("thất bại") ||
            window.location.pathname !== "/auth/callback",
      { timeout: 5000 },
    ).catch(() => null);
    expect(errorOrRedirect).toBeTruthy();
  });

  test("callback with invalid code shows error", async ({ page }) => {
    await page.goto(`${FE_URL}/auth/callback?code=invalid-code-xyz&state=invalid`);
    await page.waitForTimeout(2000);
    // FE should detect invalid state/code
    const hasError = await page
      .getByText(/thất bại|từ chối|lỗi/i)
      .isVisible()
      .catch(() => false);
    expect(hasError).toBeTruthy();
  });
});
