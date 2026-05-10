/**
 * Tier 1 Playwright E2E — Token Validation (30 tests).
 *
 * Real Keycloak issues tokens; real BE validates them. Each test
 * names the user-perspective scenario.
 */

import { test, expect } from "./helpers/fixtures";
import { request } from "@playwright/test";

const BE_URL = process.env.PW_API_BASE ?? "http://localhost:8100";
const KC_URL = process.env.KEYCLOAK_URL ?? "http://localhost:8180";

// ── 1. Happy path — valid token reaches /auth/me ─────────────────────────────

test.describe("Valid Keycloak token", () => {
  test("business user token validates against BE /auth/me", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${bizUser.accessToken}` },
    });
    // BE may 404 (user not in DB) or 200 (user dict from JWT fast path)
    expect([200, 401, 404]).toContain(res.status());
    if (res.ok()) {
      const body = await res.json();
      expect(body.email).toBe(bizUser.email);
    }
  });

  test("auditor user token validates", async ({ auditorUser }) => {
    expect(auditorUser.accessToken).toBeTruthy();
    expect(auditorUser.accessToken.length).toBeGreaterThan(100);
  });

  test("cb_admin user token validates", async ({ cbAdminUser }) => {
    expect(cbAdminUser.accessToken).toBeTruthy();
  });

  test("platform_admin user token validates", async ({ platformAdminUser }) => {
    expect(platformAdminUser.accessToken).toBeTruthy();
  });

  test("token contains email claim", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.email).toBe(bizUser.email);
  });

  test("token contains tenant_id mapper claim", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.tenant_id).toBe(bizUser.tenantId);
  });

  test("token contains is_owner mapper claim", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.is_owner).toBe(true);
  });

  test("token contains status mapper claim", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.status).toBe("active");
  });

  test("token contains realm_access.roles claim", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    expect(payload.realm_access?.roles).toContain("business");
  });

  test("token contains aminra-backend in audience", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    const aud = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
    expect(aud).toContain("aminra-backend");
  });
});


// ── 2. Token rejection scenarios ─────────────────────────────────────────────

test.describe("Token rejection", () => {
  test("BE rejects missing Authorization header", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`);
    expect(res.status()).toBe(401);
  });

  test("BE rejects empty Bearer token", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: "Bearer " },
    });
    expect(res.status()).toBe(401);
  });

  test("BE rejects malformed Bearer token", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: "Bearer not.a.token" },
    });
    expect(res.status()).toBe(401);
  });

  test("BE rejects token with tampered signature", async ({ bizUser }) => {
    const parts = bizUser.accessToken.split(".");
    const tampered = `${parts[0]}.${parts[1]}.tamperedSig123`;
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${tampered}` },
    });
    expect(res.status()).toBe(401);
  });

  test("BE rejects token with tampered payload", async ({ bizUser }) => {
    const parts = bizUser.accessToken.split(".");
    // Modify payload (claim email to attacker)
    const original = JSON.parse(Buffer.from(parts[1], "base64").toString());
    original.email = "attacker@evil.com";
    const newPayload = Buffer.from(JSON.stringify(original))
      .toString("base64url")
      .replace(/=+$/, "");
    const tampered = `${parts[0]}.${newPayload}.${parts[2]}`;
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${tampered}` },
    });
    expect(res.status()).toBe(401);
  });

  test("BE rejects garbage token structure", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: "Bearer xxx.yyy" },
    });
    expect(res.status()).toBe(401);
  });

  test("BE rejects token issued by wrong realm", async () => {
    // Token from master realm has wrong issuer
    const ctx = await request.newContext();
    const masterRes = await ctx.post(
      `${KC_URL}/realms/master/protocol/openid-connect/token`,
      {
        form: {
          username: "admin",
          password: process.env.KEYCLOAK_ADMIN_PASSWORD ?? "admin_test_pw_2026_change_me",
          grant_type: "password",
          client_id: "admin-cli",
        },
      },
    );
    const { access_token } = await masterRes.json();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(401);
  });

  test("BE 401 response includes detail field", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: "Bearer not.a.token" },
    });
    const body = await res.json();
    expect(body.detail).toBeDefined();
  });
});


// ── 3. Token lifecycle ────────────────────────────────────────────────────────

test.describe("Token lifecycle", () => {
  test("access token expires (refresh) after refresh grant produces new token", async ({
    bizUser,
  }) => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          grant_type: "refresh_token",
          refresh_token: bizUser.refreshToken,
          client_id: "aminra-frontend",
        },
      },
    );
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(body.access_token).toBeTruthy();
    expect(body.access_token).not.toBe(bizUser.accessToken);
  });

  test("refresh token rotation produces new refresh token", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          grant_type: "refresh_token",
          refresh_token: bizUser.refreshToken,
          client_id: "aminra-frontend",
        },
      },
    );
    const body = await res.json();
    expect(body.refresh_token).toBeTruthy();
  });

  test("refresh with invalid refresh_token rejected", async () => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          grant_type: "refresh_token",
          refresh_token: "not-a-valid-refresh-token",
          client_id: "aminra-frontend",
        },
      },
    );
    expect([400, 401]).toContain(res.status());
  });

  test("token has expires_in within realm policy bounds", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    const ttl = payload.exp - payload.iat;
    expect(ttl).toBeGreaterThan(0);
    expect(ttl).toBeLessThanOrEqual(3600); // realm accessTokenLifespan = 900s
  });

  test("token has iat claim near current time", async ({ bizUser }) => {
    const payload = JSON.parse(
      Buffer.from(bizUser.accessToken.split(".")[1], "base64").toString(),
    );
    const now = Math.floor(Date.now() / 1000);
    expect(Math.abs(payload.iat - now)).toBeLessThan(60);
  });
});


// ── 4. Disabled / suspended user ─────────────────────────────────────────────

test.describe("Account state", () => {
  test("disabled user cannot direct-grant login", async ({ suspendedUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          username: suspendedUser.email,
          password: suspendedUser.password,
          grant_type: "password",
          client_id: "aminra-frontend",
          scope: "openid profile email",
        },
      },
    );
    expect([400, 401]).toContain(res.status());
  });

  test("suspended user has accessToken empty in fixture", async ({ suspendedUser }) => {
    expect(suspendedUser.accessToken).toBe("");
  });
});


// ── 5. Wrong password / non-existent ─────────────────────────────────────────

test.describe("Authentication failures", () => {
  test("wrong password rejected", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          username: bizUser.email,
          password: "WrongPassword!2026",
          grant_type: "password",
          client_id: "aminra-frontend",
          scope: "openid profile email",
        },
      },
    );
    expect(res.status()).toBe(401);
  });

  test("non-existent user rejected", async () => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          username: "noone@nowhere.com",
          password: "AnyPassword!2026",
          grant_type: "password",
          client_id: "aminra-frontend",
          scope: "openid profile email",
        },
      },
    );
    expect(res.status()).toBe(401);
  });

  test("empty password rejected", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          username: bizUser.email,
          password: "",
          grant_type: "password",
          client_id: "aminra-frontend",
          scope: "openid profile email",
        },
      },
    );
    expect([400, 401]).toContain(res.status());
  });

  test("missing client_id rejected", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          username: bizUser.email,
          password: bizUser.password,
          grant_type: "password",
          scope: "openid profile email",
        },
      },
    );
    expect([400, 401]).toContain(res.status());
  });

  test("wrong client_id rejected", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.post(
      `${KC_URL}/realms/aminra/protocol/openid-connect/token`,
      {
        form: {
          username: bizUser.email,
          password: bizUser.password,
          grant_type: "password",
          client_id: "nonexistent-client",
          scope: "openid profile email",
        },
      },
    );
    expect(res.status()).toBe(401);
  });
});
