import { test, expect } from "./fixtures";

test.describe("08. UI login form — business", () => {
  test("Login form renders with email + password + submit button", async ({ page }) => {
    await page.goto("/business/login");

    const emailInput = page.locator('input[type="email"]').first();
    const pwInput    = page.locator('input[type="password"]').first();
    const submit     = page.locator('button[type="submit"]').first();

    await expect(emailInput).toBeVisible();
    await expect(pwInput).toBeVisible();
    await expect(submit).toBeVisible();

    const isDisabledInitially = await submit.isDisabled();
    test.info().annotations.push({
      type: "info",
      description: `Submit disabled on load: ${isDisabledInitially} (expected UX for controlled form)`,
    });
  });

  test("Form accepts email + password input", async ({ page }) => {
    await page.goto("/business/login");

    const email = page.locator('input[type="email"]').first();
    const pw    = page.locator('input[type="password"]').first();

    await email.fill("test@example.vn");
    await pw.fill("SomePassword123!");

    expect(await email.inputValue()).toBe("test@example.vn");
    expect(await pw.inputValue()).toBe("SomePassword123!");
  });
});
