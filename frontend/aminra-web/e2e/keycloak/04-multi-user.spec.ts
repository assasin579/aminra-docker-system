/**
 * Tier 1 Playwright E2E — Multi-user scenarios (20 tests).
 *
 * Cross-tenant isolation, role-based access, concurrent sessions,
 * admin actions affecting other users.
 */

import { test, expect } from "./helpers/fixtures";
import { request } from "@playwright/test";
import { disableUser, getAdminToken, logoutAllSessions } from "./helpers/admin-api";

const BE_URL = process.env.PW_API_BASE ?? "http://localhost:8100";
const KC_URL = process.env.KEYCLOAK_URL ?? "http://localhost:8180";


// ── 1. Cross-tenant token comparison ─────────────────────────────────────────

test.describe("Cross-tenant isolation", () => {
  test("two business users in different tenants have different tenant_id claim", async ({
    bizUser, bizUserB,
  }) => {
    const decodeTenant = (token: string) => {
      const payload = JSON.parse(
        Buffer.from(token.split(".")[1], "base64").toString(),
      );
      return payload.tenant_id;
    };
    expect(decodeTenant(bizUser.accessToken)).not.toBe(
      decodeTenant(bizUserB.accessToken),
    );
  });

  test("user A tenant_id matches their fixture spec", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.tenant_id).toBe(bizUser.tenantId);
  });

  test("user B tenant_id matches their fixture spec", async ({ bizUserB }) => {
    const payload = JSON.parse(
      Buffer.from(bizUserB.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.tenant_id).toBe(bizUserB.tenantId);
  });

  test("auditor has tenant_id null (no tenant binding)", async ({ auditorUser }) => {
    const payload = JSON.parse(
      Buffer.from(auditorUser.accessToken.split(".")[1], "base64").toString(),
    );
    // Auditor created with tenantId: null — claim should be absent or null
    expect(payload.tenant_id ?? null).toBeNull();
  });

  test("platform admin has tenant_id null", async ({ platformAdminUser }) => {
    const payload = JSON.parse(
      Buffer.from(platformAdminUser.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.tenant_id ?? null).toBeNull();
  });
});


// ── 2. Role separation ───────────────────────────────────────────────────────

test.describe("Role-based claims", () => {
  test("business user has only business role", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    const appRoles = (payload.realm_access?.roles ?? []).filter((r: string) =>
      ["business", "auditor", "cb_admin", "platform_admin"].includes(r),
    );
    expect(appRoles).toEqual(["business"]);
  });

  test("auditor user has only auditor role", async ({ auditorUser }) => {
    const payload = JSON.parse(
      Buffer.from(auditorUser.accessToken.split(".")[1], "base64").toString(),
    );
    const appRoles = (payload.realm_access?.roles ?? []).filter((r: string) =>
      ["business", "auditor", "cb_admin", "platform_admin"].includes(r),
    );
    expect(appRoles).toEqual(["auditor"]);
  });

  test("cb_admin user has only cb_admin role", async ({ cbAdminUser }) => {
    const payload = JSON.parse(
      Buffer.from(cbAdminUser.accessToken.split(".")[1], "base64").toString(),
    );
    const appRoles = (payload.realm_access?.roles ?? []).filter((r: string) =>
      ["business", "auditor", "cb_admin", "platform_admin"].includes(r),
    );
    expect(appRoles).toEqual(["cb_admin"]);
  });

  test("platform_admin user has only platform_admin role", async ({
    platformAdminUser,
  }) => {
    const payload = JSON.parse(
      Buffer.from(platformAdminUser.accessToken.split(".")[1], "base64").toString(),
    );
    const appRoles = (payload.realm_access?.roles ?? []).filter((r: string) =>
      ["business", "auditor", "cb_admin", "platform_admin"].includes(r),
    );
    expect(appRoles).toEqual(["platform_admin"]);
  });
});


// ── 3. Token uniqueness ──────────────────────────────────────────────────────

test.describe("Token uniqueness", () => {
  test("two different users have different access tokens", async ({
    bizUser, auditorUser,
  }) => {
    expect(bizUser.accessToken).not.toBe(auditorUser.accessToken);
  });

  test("same user logged in twice has different access tokens", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          username: bizUser.email,
          password: bizUser.password,
          grant_type: "password",
          client_id: "aminra-frontend",
          scope: "openid profile email",
        },
      },
    );
    const { access_token } = await res.json();
    // Each grant produces fresh token; iat is different
    expect(access_token).not.toBe(bizUser.accessToken);
  });
});


// ── 4. Admin operations affecting users ──────────────────────────────────────

test.describe("Admin actions on users", () => {
  test("disabling user invalidates future logins", async ({ bizUserB, adminToken }) => {
    await disableUser(adminToken, bizUserB.id);
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          username: bizUserB.email,
          password: bizUserB.password,
          grant_type: "password",
          client_id: "aminra-frontend",
          scope: "openid profile email",
        },
      },
    );
    expect(res.status()).toBeGreaterThanOrEqual(400);
  });

  test("logout-all-sessions endpoint exists for admin", async ({ bizUser, adminToken }) => {
    await logoutAllSessions(adminToken, bizUser.id);
    // Existing access token may still be valid until exp (Keycloak doesn't revoke
    // access tokens); refresh tokens are invalidated. Test admin API succeeded.
  });
});


// ── 5. Token refresh by different users in parallel ──────────────────────────

test.describe("Concurrent token operations", () => {
  test("two users refresh tokens simultaneously without crossover", async ({
    bizUser, bizUserB,
  }) => {
    const ctx = await request.newContext();
    const [r1, r2] = await Promise.all([
      ctx.post(`${KC_URL}/realms/aminra/protocol/openid-connect/token`, {
        form: {
          grant_type: "refresh_token",
          refresh_token: bizUser.refreshToken,
          client_id: "aminra-frontend",
        },
      }),
      ctx.post(`${KC_URL}/realms/aminra/protocol/openid-connect/token`, {
        form: {
          grant_type: "refresh_token",
          refresh_token: bizUserB.refreshToken,
          client_id: "aminra-frontend",
        },
      }),
    ]);
    expect(r1.ok()).toBe(true);
    expect(r2.ok()).toBe(true);
    const b1 = await r1.json();
    const b2 = await r2.json();
    const decode = (t: string) =>
      JSON.parse(Buffer.from(t.split(".")[1], "base64").toString());
    expect(decode(b1.access_token).email).toBe(bizUser.email);
    expect(decode(b2.access_token).email).toBe(bizUserB.email);
  });
});


// ── 6. JWKs endpoint discoverability ─────────────────────────────────────────

test.describe("Realm OIDC discovery", () => {
  test("OIDC discovery endpoint reachable", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(
      `${KC_URL}/realms/aminra/.well-known/openid-configuration`,
    );
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(body.issuer).toBeTruthy();
    expect(body.jwks_uri).toBeTruthy();
  });

  test("JWKs endpoint returns at least one key", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(
      `${KC_URL}/realms/aminra/protocol/openid-connect/certs`,
    );
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(Array.isArray(body.keys)).toBe(true);
    expect(body.keys.length).toBeGreaterThan(0);
  });

  test("JWKs keys have RSA kty", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(
      `${KC_URL}/realms/aminra/protocol/openid-connect/certs`,
    );
    const body = await res.json();
    const sigKey = body.keys.find((k: any) => k.use === "sig");
    expect(sigKey?.kty).toBe("RSA");
  });

  test("issuer in discovery doc matches token iss claim", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const disc = await ctx.get(
      `${KC_URL}/realms/aminra/.well-known/openid-configuration`,
    );
    const { issuer } = await disc.json();
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.iss).toBe(issuer);
  });

  test("token endpoint URL in discovery doc is correct", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(
      `${KC_URL}/realms/aminra/.well-known/openid-configuration`,
    );
    const body = await res.json();
    expect(body.token_endpoint).toContain("/protocol/openid-connect/token");
  });

  test("authorization endpoint URL exists", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(
      `${KC_URL}/realms/aminra/.well-known/openid-configuration`,
    );
    const body = await res.json();
    expect(body.authorization_endpoint).toContain(
      "/protocol/openid-connect/auth",
    );
  });
});
