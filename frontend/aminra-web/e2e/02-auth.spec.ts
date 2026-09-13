import { test, expect } from "./fixtures";
import { keycloakPasswordGrant } from "./helpers/auth-token";

test.describe("02. Authentication flows", () => {
  test("Seeded business Keycloak login returns JWT", async ({ biz }) => {
    expect(biz.token).toBeTruthy();
    expect(biz.token.length).toBeGreaterThan(20);
  });

  test("/auth/me returns correct email for business token", async ({
    api,
    biz,
  }) => {
    const r = await api.get("/auth/me", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.email).toBe(biz.email);
    expect(body.role).toBe("business");
  });

  test("Wrong password rejected 401", async ({ api, biz }) => {
    const r = await keycloakPasswordGrant(api, {
      email: biz.email,
      password: "wrongpassword",
    });
    expect([400, 401]).toContain(r.status());
  });

  test("Nonexistent email rejected", async ({ api }) => {
    const r = await keycloakPasswordGrant(api, {
      email: `never-${Date.now()}@nowhere.vn`,
      password: "x",
    });
    expect([400, 401]).toContain(r.status());
  });

  test("Duplicate email returns 409/422", async ({ api, biz }) => {
    const r = await api.post("/auth/business/register", {
      data: { email: biz.email, password: "NewPass123!", company_name: "Dup" },
    });
    expect([400, 409, 422]).toContain(r.status());
  });

  test("Admin Keycloak token is available", async ({ admin }) => {
    expect(admin.token).toBeTruthy();
  });
});
