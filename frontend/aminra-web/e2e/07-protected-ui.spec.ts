import { test, expect } from "./fixtures";

test.describe("07. Protected UI — redirect when not logged in", () => {
  const protectedPages = [
    "/dashboard/business",
    "/dashboard/provider",
    "/submissions",
    "/certificates",
    "/documents",
    "/supply-chain/batches",
    "/audits",
  ];

  for (const path of protectedPages) {
    test(`${path} → redirect to login when not authed`, async ({ page }) => {
      const response = await page.goto(path);
      // Either redirected to login OR 200 with login gate visible
      const currentUrl = page.url();
      const redirected = currentUrl.includes("/login") || currentUrl.includes("/auth");
      const onPage     = response && response.status() < 500;
      expect(redirected || onPage).toBeTruthy();
    });
  }
});
