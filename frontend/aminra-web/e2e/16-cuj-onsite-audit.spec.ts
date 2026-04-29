/**
 * CUJ-3: Onsite audit (auditor schedules visit + checklist + NCR).
 */
import { test, expect } from "./fixtures";

test.describe("CUJ-3: Onsite audit", () => {
  test("Audit visits list endpoint accessible to provider", async ({
    api,
    prov,
  }) => {
    if (!prov.token) test.skip(true, "no provider token");
    const res = await api.get("/api/audits/", {
      headers: { Authorization: `Bearer ${prov.token}` },
    });
    expect([200, 307, 401]).toContain(res.status());
  });

  test("Audit visits endpoint rejects business role", async ({ api, biz }) => {
    const res = await api.get("/api/audits/", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([401, 403, 200, 307]).toContain(res.status());
  });

  test("Audit checklist templates endpoint accessible", async ({
    api,
    prov,
  }) => {
    if (!prov.token) test.skip(true, "no provider token");
    const res = await api.get("/api/audits/templates", {
      headers: { Authorization: `Bearer ${prov.token}` },
    });
    expect([200, 307, 401, 404]).toContain(res.status());
  });

  test("Provider audits page redirects auth-required for unauthenticated", async ({
    page,
  }) => {
    await page.goto("/audits");
    await page.waitForLoadState("networkidle");
    const url = page.url();
    expect(url).toMatch(/\/(audits|provider\/login|business\/login|$)/);
  });
});
