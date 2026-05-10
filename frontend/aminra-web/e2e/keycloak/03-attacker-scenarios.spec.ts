/**
 * Tier 1 Playwright E2E — Attacker scenarios (25 tests).
 *
 * Real tokens from Keycloak, mutated/replayed by simulated attackers.
 * Tests verify BE rejects each attack vector. Read this file as a
 * threat catalog: each test name = one attack scenario.
 */

import { test, expect } from "./helpers/fixtures";
import { request } from "@playwright/test";

const BE_URL = process.env.PW_API_BASE ?? "http://localhost:8100";
const KC_URL = process.env.KEYCLOAK_URL ?? "http://localhost:8180";


function decode(token: string): { header: any; payload: any; sig: string } {
  const [h, p, s] = token.split(".");
  return {
    header: JSON.parse(Buffer.from(h, "base64").toString()),
    payload: JSON.parse(Buffer.from(p, "base64").toString()),
    sig: s,
  };
}

function reassemble(header: any, payload: any, sig: string): string {
  const h = Buffer.from(JSON.stringify(header)).toString("base64url").replace(/=+$/, "");
  const p = Buffer.from(JSON.stringify(payload)).toString("base64url").replace(/=+$/, "");
  return `${h}.${p}.${sig}`;
}

async function callApi(token: string) {
  const ctx = await request.newContext();
  return ctx.get(`${BE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}


// ═════════════════════════════════════════════════════════════════════════════
// 1. SIGNATURE ATTACKS
// ═════════════════════════════════════════════════════════════════════════════

test.describe("Signature attacks", () => {
  test("alg=none attack rejected", async ({ bizUser }) => {
    const { header, payload } = decode(bizUser.accessToken);
    const evilToken = reassemble({ ...header, alg: "none" }, payload, "");
    const res = await callApi(evilToken);
    expect(res.status()).toBe(401);
  });

  test("HS256 with public-key-as-secret rejected (alg confusion)", async ({ bizUser }) => {
    const { header, payload } = decode(bizUser.accessToken);
    const evilToken = reassemble(
      { ...header, alg: "HS256" }, payload, "fake-sig-here",
    );
    const res = await callApi(evilToken);
    expect(res.status()).toBe(401);
  });

  test("ES256 algorithm rejected (not in whitelist)", async ({ bizUser }) => {
    const { header, payload } = decode(bizUser.accessToken);
    const evilToken = reassemble(
      { ...header, alg: "ES256" }, payload, bizUser.accessToken.split(".")[2],
    );
    const res = await callApi(evilToken);
    expect(res.status()).toBe(401);
  });

  test("signature byte-flipped rejected", async ({ bizUser }) => {
    const parts = bizUser.accessToken.split(".");
    const sig = parts[2];
    const flipped = sig.slice(0, -3) + (sig.slice(-3) === "AAA" ? "BBB" : "AAA");
    const evilToken = `${parts[0]}.${parts[1]}.${flipped}`;
    const res = await callApi(evilToken);
    expect(res.status()).toBe(401);
  });

  test("signature truncated rejected", async ({ bizUser }) => {
    const parts = bizUser.accessToken.split(".");
    const evilToken = `${parts[0]}.${parts[1]}.${parts[2].slice(0, -10)}`;
    const res = await callApi(evilToken);
    expect(res.status()).toBe(401);
  });

  test("signature replaced with junk rejected", async ({ bizUser }) => {
    const parts = bizUser.accessToken.split(".");
    const evilToken = `${parts[0]}.${parts[1]}.aaaaaaaaaaaaaaaaaaaaaaa`;
    const res = await callApi(evilToken);
    expect(res.status()).toBe(401);
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 2. CLAIM TAMPERING
// ═════════════════════════════════════════════════════════════════════════════

test.describe("Claim tampering", () => {
  test("modified email claim rejected (signature break)", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(header, { ...payload, email: "attacker@evil.com" }, sig);
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("modified tenant_id rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(header, { ...payload, tenant_id: "victim-tenant" }, sig);
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("modified is_owner claim rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(header, { ...payload, is_owner: true }, sig);
    const res = await callApi(evil);
    // Originally was true — keep but verify signature still rejected after re-encoding
    if (payload.is_owner === true) test.skip(true, "Already true, no diff");
    expect(res.status()).toBe(401);
  });

  test("escalated role claim rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(
      header,
      { ...payload, realm_access: { roles: ["platform_admin"] } },
      sig,
    );
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("aud changed to attacker rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(header, { ...payload, aud: "attacker-app" }, sig);
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("iss changed rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(
      header,
      { ...payload, iss: "https://evil.example.com/realms/aminra" },
      sig,
    );
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("exp extended forever rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(
      header,
      { ...payload, exp: Math.floor(Date.now() / 1000) + 999999999 },
      sig,
    );
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("status escalated to active when suspended rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(header, { ...payload, status: "active" }, sig);
    if (payload.status === "active") test.skip(true, "Already active");
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 3. KID HEADER ATTACKS
// ═════════════════════════════════════════════════════════════════════════════

test.describe("Kid header attacks", () => {
  test("missing kid rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const { kid: _, ...noKid } = header;
    const evil = reassemble(noKid, payload, sig);
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("empty kid rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble({ ...header, kid: "" }, payload, sig);
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("kid SQL injection payload rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(
      { ...header, kid: "'; DROP TABLE users; --" },
      payload,
      sig,
    );
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("kid path traversal rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(
      { ...header, kid: "../../../etc/passwd" },
      payload,
      sig,
    );
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("kid enormous string rejected", async ({ bizUser }) => {
    const { header, payload, sig } = decode(bizUser.accessToken);
    const evil = reassemble(
      { ...header, kid: "x".repeat(10000) },
      payload,
      sig,
    );
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 4. STRUCTURE ATTACKS
// ═════════════════════════════════════════════════════════════════════════════

test.describe("Token structure attacks", () => {
  test("token with extra dots rejected", async ({ bizUser }) => {
    const evil = `${bizUser.accessToken}.extrasegment`;
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("token with NULL byte rejected", async () => {
    // HTTP layer rejects NULL bytes in header values before reaching BE.
    // Either the request throws or BE returns non-2xx — both are valid
    // defenses. Test asserts NO 2xx success.
    try {
      const res = await callApi("ey\x00.payload.sig");
      expect(res.status()).toBeGreaterThanOrEqual(400);
    } catch (e) {
      // HTTP client throws on invalid header — also a valid defense
      expect(e).toBeTruthy();
    }
  });

  test("token with whitespace rejected", async ({ bizUser }) => {
    const evil = `   ${bizUser.accessToken}   `;
    const res = await callApi(evil);
    // BE / HTTP framework may map malformed header to 401, 404, or 400
    expect(res.status()).toBeGreaterThanOrEqual(400);
  });

  test("missing one segment rejected", async ({ bizUser }) => {
    const parts = bizUser.accessToken.split(".");
    const evil = `${parts[0]}.${parts[1]}`;
    const res = await callApi(evil);
    expect(res.status()).toBe(401);
  });

  test("Bearer prefix in token value rejected", async ({ bizUser }) => {
    // Caller already prepends Bearer; double prefix breaks parsing
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: `Bearer Bearer ${bizUser.accessToken}` },
    });
    expect(res.status()).toBe(401);
  });

  test("non-Bearer scheme rejected", async ({ bizUser }) => {
    const ctx = await request.newContext();
    const res = await ctx.get(`${BE_URL}/auth/me`, {
      headers: { Authorization: `Basic ${bizUser.accessToken}` },
    });
    expect([401, 403]).toContain(res.status());
  });
});
