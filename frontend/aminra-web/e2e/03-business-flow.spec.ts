import { test, expect } from "./fixtures";

test.describe("03. Business user workflow", () => {
  test("Business can view empty submissions list", async ({ api, biz }) => {
    const r = await api.get("/api/submissions/my-submissions", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(Array.isArray(body) || typeof body === "object").toBeTruthy();
  });

  test("Business can view company profile", async ({ api, biz }) => {
    const r = await api.get("/auth/company-profile", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });

  test("Business can update company profile", async ({ api, biz }) => {
    const r = await api.put("/auth/company-profile", {
      headers: { Authorization: `Bearer ${biz.token}` },
      data: { company_name: "Updated PW Co", address: "123 Test St" },
    });
    expect([200, 204]).toContain(r.status());
  });

  test("Business can list assessment templates", async ({ api, biz }) => {
    const r = await api.get("/api/assessments/templates", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });

  test("Business can list documents", async ({ api, biz }) => {
    const r = await api.get("/api/documents", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });

  test("Business blocked from admin users endpoint", async ({ api, biz }) => {
    const r = await api.get("/admin/users", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([401, 403, 404]).toContain(r.status());
  });
});
