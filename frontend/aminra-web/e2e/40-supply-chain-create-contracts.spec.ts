import { test, expect, request as playwrightRequest, APIRequestContext } from "@playwright/test";
import { requireKeycloakUserToken } from "./helpers/auth-token";

const FRONTEND_URL = (process.env.FRONTEND_URL || "http://127.0.0.1:3100").replace(/\/$/, "");
const DEMO_EMAIL = process.env.PW_BIZ_EMAIL || process.env.DEMO_BUSINESS_EMAIL || "biz-demo-1@demo.aminra.vn";
const DEMO_PW = process.env.PW_BIZ_PASSWORD || process.env.DEMO_PW;

async function getBusinessToken(api: APIRequestContext): Promise<string> {
  if (!DEMO_PW) test.skip(true, "business demo password not configured (PW_BIZ_PASSWORD or DEMO_PW)");
  return requireKeycloakUserToken(api, { email: DEMO_EMAIL, password: DEMO_PW as string });
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
