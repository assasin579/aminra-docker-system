import { test, expect, request } from "@playwright/test";

const API_BASE = process.env.PW_API_BASE ?? "http://localhost:8100";
const KC_URL = process.env.KEYCLOAK_URL ?? "https://auth.silvergem.org";
const KC_REALM = process.env.KEYCLOAK_REALM ?? "aminra";
const KC_CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID ?? "aminra-frontend";
const DEMO_PW = process.env.DEMO_PW ?? "DemoP@ss2026";
const PROVIDER_DEMO_PW = process.env.PROVIDER_DEMO_PW ?? DEMO_PW;
const DEMO_CERT = "HALAL-2026-DEMO";
const DEMO_TRACE_PUBLIC_ID = "73695b8a-3c10-570b-8bba-92c12da9b56e";
const DEMO_TRACE_BATCH = "QA-TRACE-PUBLISHED-SEALED-001";

async function keycloakToken(email: string, password = DEMO_PW): Promise<string | null> {
  const ctx = await request.newContext();
  const res = await ctx.post(`${KC_URL}/realms/${KC_REALM}/protocol/openid-connect/token`, {
    form: {
      grant_type: "password",
      client_id: KC_CLIENT_ID,
      username: email,
      password,
    },
  });
  const body = await res.json().catch(() => ({}));
  await ctx.dispose();
  return res.status() === 200 && body.access_token ? body.access_token : null;
}

test.describe("P0 browser/API demo spine with Keycloak", () => {
  test("anonymous public pages and public APIs render safe demo data", async ({ page }) => {
    await page.goto(`/verify/${DEMO_CERT}`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(DEMO_CERT).first()).toBeVisible();
    await expect(page.getByText(/Chứng nhận hợp lệ|Certificate valid/i).first()).toBeVisible();

    await page.goto(`/trace/${DEMO_TRACE_PUBLIC_ID}`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(DEMO_TRACE_BATCH).first()).toBeVisible();

    await page.goto("/forgot-password");
    await expect(page).toHaveURL(/forgot-password|auth\.silvergem\.org/);
  });

  test("business token can reach protected demo spine endpoints", async () => {
    const token = await keycloakToken("biz-demo-1@demo.aminra.vn");
    test.skip(!token, "seeded business Keycloak user missing");

    const api = await request.newContext({ baseURL: API_BASE, extraHTTPHeaders: { Authorization: `Bearer ${token}` } });
    for (const path of [
      "/api/documents",
      "/api/submissions/my-submissions",
      "/dossiers",
      "/api/supply-chain/suppliers",
      "/api/supply-chain/materials",
      "/api/supply-chain/processes",
      "/api/supply-chain/batches",
    ]) {
      const res = await api.get(path);
      expect(res.status(), path).toBe(200);
    }
    await api.dispose();
  });

  test("provider token can reach provider demo spine endpoints and business is denied provider-only action", async () => {
    const providerToken = await keycloakToken("cb-demo@demo.aminra.vn", PROVIDER_DEMO_PW);
    const businessToken = await keycloakToken("biz-demo-1@demo.aminra.vn");
    test.skip(!providerToken || !businessToken, "seeded Keycloak users missing");

    const providerApi = await request.newContext({ baseURL: API_BASE, extraHTTPHeaders: { Authorization: `Bearer ${providerToken}` } });
    for (const path of [
      "/api/submissions/received",
      "/api/submissions/cb-stats",
      "/api/submissions/certificates/registry",
      "/api/audits/",
    ]) {
      const res = await providerApi.get(path);
      expect(res.status(), path).toBe(200);
    }
    await providerApi.dispose();

    const businessApi = await request.newContext({ baseURL: API_BASE, extraHTTPHeaders: { Authorization: `Bearer ${businessToken}` } });
    const denied = await businessApi.post("/api/submissions/issue-certificate/00000000-0000-0000-0000-000000000000", {
      data: { expiry_months: 12, notes: "" },
    });
    expect(denied.status()).toBe(403);
    await businessApi.dispose();
  });
});
