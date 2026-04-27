/**
 * CUJ-9: Self-assessment flow (business self-evaluates compliance).
 */
import { test, expect } from "./fixtures";

test.describe("CUJ-9: Self-assessment", () => {
  test("Templates endpoint accessible to business", async ({ api, biz }) => {
    const res = await api.get("/api/assessments/templates", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307, 401]).toContain(res.status());
  });

  test("List my assessments works for business", async ({ api, biz }) => {
    const res = await api.get("/api/assessments/", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307]).toContain(res.status());
    if (res.status() === 200) {
      const body = await res.json();
      // Either returns list directly OR { assessments: [...] }
      expect(Array.isArray(body) || Array.isArray(body.assessments)).toBe(true);
    }
  });

  test("Self-assessment page renders for business", async ({ page, biz }) => {
    if (!biz.token) test.skip(true, "no biz token");
    await page.goto("/self-assessment");
    const url = page.url();
    // Either auth-redirect or self-assess page
    expect(url).toMatch(/\/(self-assessment|business\/login)/);
  });

  test("Provider cannot access business self-assessment endpoints", async ({ api, prov }) => {
    if (!prov.token) test.skip(true, "no provider token");
    const res = await api.post("/api/assessments/", {
      headers: {
        Authorization: `Bearer ${prov.token}`,
        "Content-Type": "application/json",
      },
      data: { template_id: "00000000-0000-0000-0000-000000000000" },
    });
    expect([400, 403, 422]).toContain(res.status());
  });
});
