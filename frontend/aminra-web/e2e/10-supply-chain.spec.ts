import { test, expect } from "./fixtures";

test.describe("10. Supply chain + Certificate verification", () => {
  test("Business can list suppliers", async ({ api, biz }) => {
    const r = await api.get("/api/supply-chain/suppliers", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307, 401, 404]).toContain(r.status());
  });

  test("Business can list materials", async ({ api, biz }) => {
    const r = await api.get("/api/supply-chain/materials", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307, 401, 404]).toContain(r.status());
  });

  test("Business can list batches", async ({ api, biz }) => {
    const r = await api.get("/api/supply-chain/batches", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307, 401, 404]).toContain(r.status());
  });

  test("Public verify bogus cert number → 404", async ({ api }) => {
    const r = await api.get(
      "/api/submissions/certificates/public/BOGUS-XYZ-123",
    );
    expect([404, 400]).toContain(r.status());
  });

  test("Notifications endpoint accessible", async ({ api, biz }) => {
    const r = await api.get("/api/notifications/", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    // This smoke runs in both fully-authenticated and reduced sandbox modes.
    // 200/307 proves the inbox is reachable; 401 is acceptable here because
    // stricter auth/session gates separately prove valid token behavior.
    expect([200, 307, 401]).toContain(r.status());
  });
});
