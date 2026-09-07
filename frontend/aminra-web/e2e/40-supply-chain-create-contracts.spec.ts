import { test, expect, request as playwrightRequest, APIRequestContext } from "@playwright/test";

const FRONTEND_URL = (process.env.FRONTEND_URL || "http://127.0.0.1:3100").replace(/\/$/, "");
const KEYCLOAK_URL = (process.env.KEYCLOAK_TOKEN_URL || "http://127.0.0.1:8180").replace(/\/$/, "");
const REALM = process.env.KEYCLOAK_REALM || "aminra";
const CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID || "aminra-frontend";
const DEMO_EMAIL = process.env.DEMO_BUSINESS_EMAIL || "biz-demo-1@demo.aminra.vn";
const DEMO_PW = process.env.DEMO_PW || "DemoP@ss2026";

async function getBusinessToken(api: APIRequestContext): Promise<string> {
  const form = new URLSearchParams({
    grant_type: "password",
    client_id: CLIENT_ID,
    username: DEMO_EMAIL,
    password: DEMO_PW,
  });
  const resp = await api.post(`${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token`, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-Forwarded-Proto": process.env.KEYCLOAK_PUBLIC_PROTO || "https",
      "X-Forwarded-Host": process.env.KEYCLOAK_PUBLIC_HOST || "auth.silvergem.org",
      "X-Forwarded-Port": process.env.KEYCLOAK_PUBLIC_PORT || "443",
    },
    data: form.toString(),
  });
  expect(resp.status(), await resp.text()).toBe(200);
  const body = await resp.json();
  return body.access_token;
}

test.describe("Supply-chain FE proxy create-contract smoke", () => {
  test("process, supplier, and batch create flows reach backend through /api/api", async () => {
    const api = await playwrightRequest.newContext({ ignoreHTTPSErrors: true });
    const token = await getBusinessToken(api);
    const headers = { Authorization: `Bearer ${token}` };
    const stamp = Date.now();
    const created: { kind: "processes" | "suppliers" | "batches"; id: string }[] = [];

    try {
      const processResp = await api.post(`${FRONTEND_URL}/api/api/supply-chain/processes`, {
        headers,
        data: { name: `QA contract process ${stamp}` },
      });
      expect(processResp.status(), await processResp.text()).toBe(200);
      const processBody = await processResp.json();
      expect(processBody.id).toMatch(/^[0-9a-f-]{36}$/i);
      created.push({ kind: "processes", id: processBody.id });

      const supplierResp = await api.post(`${FRONTEND_URL}/api/api/supply-chain/suppliers`, {
        headers,
        data: { name: `QA contract supplier ${stamp}`, supplier_type: "manufacturer" },
      });
      expect(supplierResp.status(), await supplierResp.text()).toBe(200);
      const supplierBody = await supplierResp.json();
      expect(supplierBody.id).toMatch(/^[0-9a-f-]{36}$/i);
      created.push({ kind: "suppliers", id: supplierBody.id });

      const batchResp = await api.post(`${FRONTEND_URL}/api/api/supply-chain/batches`, {
        headers,
        data: {
          product_name: `QA contract batch ${stamp}`,
          process_template_id: processBody.id,
          materials: [],
        },
      });
      expect(batchResp.status(), await batchResp.text()).toBe(200);
      const batchBody = await batchResp.json();
      expect(batchBody.id).toMatch(/^[0-9a-f-]{36}$/i);
      created.push({ kind: "batches", id: batchBody.id });
    } finally {
      for (const item of created.reverse()) {
        await api.delete(`${FRONTEND_URL}/api/api/supply-chain/${item.kind}/${item.id}`, { headers }).catch(() => undefined);
      }
      await api.dispose();
    }
  });
});
