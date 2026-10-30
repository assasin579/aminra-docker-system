import { test, expect } from "./fixtures";

test.describe("08. UI login form — business", () => {
  test("Login form renders with email + password + submit button", async ({
    page,
  }) => {
    await page.goto("/business/login");

    const emailInput = page.locator('input[type="email"]').first();
    const pwInput = page.locator('input[type="password"]').first();
    const submit = page.locator('button[type="submit"]').first();

    await expect(emailInput).toBeVisible();
    await expect(pwInput).toBeVisible();
    await expect(submit).toBeVisible();

    const isDisabledInitially = await submit.isDisabled();
    test.info().annotations.push({
      type: "info",
      description: `Submit disabled on load: ${isDisabledInitially} (expected UX for controlled form)`,
    });
  });

  test("Form exposes editable email + password controls", async ({ page }) => {
    await page.goto("/business/login");

    const email = page.getByPlaceholder("cong ty@example.com");
    const pw = page.getByPlaceholder("••••••••");

    await expect(email).toBeEditable();
    await expect(pw).toBeEditable();
  });

  test("Login page lets unauthenticated users return to the landing page", async ({
    page,
  }) => {
    await page.goto("/business/login");

    const exit = page.getByRole("link", { name: "Về trang chủ" });
    await expect(exit).toBeVisible();
    await expect(exit).toHaveAttribute("href", "/landing");

    const href = await exit.getAttribute("href");
    expect(href).toBe("/landing");
    await page.goto(href!, { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/landing$/);
  });
});
