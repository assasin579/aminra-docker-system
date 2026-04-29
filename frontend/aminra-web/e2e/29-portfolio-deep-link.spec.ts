/**
 * Portfolio "Xem hồ sơ" → submissions deep-link.
 *
 * Bug 2026-04-26: clicking "Xem hồ sơ" on a business card in /portfolio
 * navigated to the generic /submissions list — provider had to make an
 * extra click to drill into that company's folder.
 *
 * Fix: portfolio link now passes ?company=<name>; submissions page reads it
 * via useSearchParams + initializes `selectedCompany` to that value.
 */
import { test, expect } from "@playwright/test";

const PROVIDER_LOGIN = {
  email: "cb-demo@demo.aminra.vn",
  password: "DemoP@ss2026",
  role: "provider",
};

test.describe("portfolio deep-link to company folder", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "deep-link UX only needs desktop coverage",
    );
  });

  test("submissions page lands on company folder when ?company= passed", async ({
    page,
    request,
  }) => {
    const login = await request.post("/api/auth/login", {
      data: PROVIDER_LOGIN,
    });
    if (!login.ok()) test.skip(true, "cb-demo not seeded");
    const { access_token, user } = await login.json();

    // Find a real business name from the provider's submissions.
    const sublist = await request.get("/api/api/submissions/received", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(sublist.ok()).toBeTruthy();
    const { submissions } = await sublist.json();
    const companies = Array.from(
      new Set(
        (submissions ?? [])
          .map((s: { company_name: string }) => s.company_name)
          .filter(Boolean),
      ),
    );
    if (companies.length === 0)
      test.skip(true, "no submissions to test against");
    const target = companies[0] as string;

    await page.addInitScript(
      ({ t, u }) => {
        localStorage.setItem("aminra_user_token", t);
        localStorage.setItem("aminra_user_profile", u);
      },
      { t: access_token, u: JSON.stringify(user) },
    );

    await page.goto(`/submissions?company=${encodeURIComponent(target)}`);

    // Page must show the company name as the heading (folder view), not the
    // generic "Hồ sơ nhận được" label.
    await expect(page.getByRole("heading", { name: target })).toBeVisible({
      timeout: 10000,
    });

    // The "back" link to leave the folder must be visible (means we're inside).
    await expect(page.getByText(`Quay lại · ${target}`)).toBeVisible();
  });

  test("portfolio link includes ?company= deep-link (static check)", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile(
      "../../frontend/aminra-web/app/portfolio/page.tsx",
      "utf8",
    ).catch(() => readFile("app/portfolio/page.tsx", "utf8"));
    expect(
      src,
      "portfolio 'Xem hồ sơ' link must pass company query param",
    ).toMatch(
      /\/submissions\?company=\$\{encodeURIComponent\(biz\.company_name\)\}/,
    );
  });

  /**
   * Real UI flow: navigate to /portfolio, expand a business card, click the
   * actual "Xem hồ sơ" link, and verify the destination shows the company
   * folder (not the generic list).
   */
  test("UI flow: click 'Xem hồ sơ' on portfolio → lands on company folder", async ({
    page,
    request,
  }) => {
    const login = await request.post("/api/auth/login", {
      data: PROVIDER_LOGIN,
    });
    if (!login.ok()) test.skip(true, "cb-demo not seeded");
    const { access_token, user } = await login.json();

    // Find a real business name with submissions.
    const bizListRes = await request.get("/api/api/audits/businesses", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const { businesses } = await bizListRes.json();
    const subList = await request.get("/api/api/submissions/received", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const { submissions } = await subList.json();
    const companiesWithSubs = new Set(
      (submissions ?? []).map((s: { company_name: string }) => s.company_name),
    );
    const target = (businesses ?? []).find((b: { company_name: string }) =>
      companiesWithSubs.has(b.company_name),
    );
    if (!target) test.skip(true, "no business has submissions to drill into");

    await page.addInitScript(
      ({ t, u }) => {
        localStorage.setItem("aminra_user_token", t);
        localStorage.setItem("aminra_user_profile", u);
      },
      { t: access_token, u: JSON.stringify(user) },
    );

    await page.goto("/portfolio");

    // Expand the target business card to reveal action buttons.
    await page
      .getByRole("button", { name: new RegExp(target.company_name) })
      .first()
      .click();

    // Click the "Xem hồ sơ" link inside the expanded section.
    const xemHoSo = page.getByRole("link", { name: "Xem hồ sơ" }).first();
    await expect(xemHoSo).toBeVisible();
    const href = await xemHoSo.getAttribute("href");
    expect(href, "link must encode company name in query").toMatch(
      new RegExp(
        `/submissions\\?company=${encodeURIComponent(target.company_name).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`,
      ),
    );

    await xemHoSo.click();
    await page.waitForURL(/\/submissions\?company=/);

    // Folder header must show the company name (not generic "Hồ sơ nhận được").
    await expect(
      page.getByRole("heading", { name: target.company_name }),
    ).toBeVisible({ timeout: 10000 });
    // Back link confirms we're inside the folder, not the company list.
    await expect(
      page.getByText(`Quay lại · ${target.company_name}`),
    ).toBeVisible();
  });
});
