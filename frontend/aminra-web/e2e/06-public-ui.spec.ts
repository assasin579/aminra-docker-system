import { test, expect } from "./fixtures";

test.describe("06. Public-facing UI pages", () => {
  const publicPages = [
    { path: "/", title: /Aminra|Halal/i },
    { path: "/landing", title: /.+/ },
    { path: "/business/login", title: /.+/ },
    { path: "/business/register", title: /.+/ },
    { path: "/provider/login", title: /.+/ },
    { path: "/provider/register", title: /.+/ },
  ];

  for (const { path, title } of publicPages) {
    test(`${path} renders with title`, async ({ page }) => {
      const response = await page.goto(path);
      expect(response?.status()).toBeLessThan(500);
      await expect(page).toHaveTitle(title);
    });
  }

  test("Business login form has email + password fields", async ({ page }) => {
    await page.goto("/business/login");
    await expect(
      page.locator("input[type=email], input[name*=email i]").first(),
    ).toBeVisible();
    await expect(page.locator("input[type=password]").first()).toBeVisible();
  });

  test("Business register form has required fields", async ({ page }) => {
    await page.goto("/business/register");
    await expect(
      page.locator("input[type=email], input[name*=email i]").first(),
    ).toBeVisible();
    await expect(page.locator("input[type=password]").first()).toBeVisible();
  });
});
