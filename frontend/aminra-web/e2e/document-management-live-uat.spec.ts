import { expect, test } from "@playwright/test";
import { requireKeycloakUserToken } from "./helpers/auth-token";

const API_BASE = (process.env.PW_API_BASE || "http://localhost:8100").replace(/\/$/, "");
const businessEmail = process.env.PW_BIZ_EMAIL || process.env.DEMO_BUSINESS_EMAIL || "biz-demo-1@demo.aminra.vn";
const businessPassword = process.env.PW_BIZ_PASSWORD || process.env.DEMO_PW;
const providerEmail = process.env.PW_PROVIDER_EMAIL || "cb-demo@demo.aminra.vn";
const providerPassword = process.env.PW_PROVIDER_PASSWORD || process.env.PROVIDER_DEMO_PW || process.env.DEMO_PW;

function requireSecret(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing ${name}; source .qa/aminra-demo-credentials.env or run scripts/qa/repair-demo-accounts.sh`);
  }
  return value;
}

test.describe("document management live API UAT", () => {
  test("business can upload/list/detail/download/delete document while forbidden roles stay blocked", async ({ request }) => {
    const businessToken = await requireKeycloakUserToken(request, {
      email: businessEmail,
      password: requireSecret("PW_BIZ_PASSWORD", businessPassword),
    });
    const providerToken = await requireKeycloakUserToken(request, {
      email: providerEmail,
      password: requireSecret("PW_PROVIDER_PASSWORD", providerPassword),
    });

    const noAuth = await request.get(`${API_BASE}/api/documents`);
    expect([401, 403]).toContain(noAuth.status());

    const providerUpload = await request.post(`${API_BASE}/api/documents/upload`, {
      headers: { Authorization: `Bearer ${providerToken}` },
      multipart: {
        doc_type: "halal_policy",
        file: {
          name: "provider-forbidden-document.txt",
          mimeType: "text/plain",
          buffer: Buffer.from("provider upload must be forbidden"),
        },
      },
    });
    expect(providerUpload.status()).toBe(403);

    const fileName = `document-live-uat-${Date.now()}.txt`;
    const upload = await request.post(`${API_BASE}/api/documents/upload`, {
      headers: { Authorization: `Bearer ${businessToken}` },
      multipart: {
        doc_type: "halal_policy",
        file: {
          name: fileName,
          mimeType: "text/plain",
          buffer: Buffer.from("AMINRA document live UAT sample"),
        },
      },
    });
    expect(upload.status(), await upload.text()).toBe(200);
    const uploaded = await upload.json();
    expect(uploaded.id).toMatch(/^[0-9a-f-]{36}$/i);
    expect(uploaded.filename).toBe(fileName);

    const docId = uploaded.id as string;
    try {
      const list = await request.get(`${API_BASE}/api/documents?doc_type=halal_policy`, {
        headers: { Authorization: `Bearer ${businessToken}` },
      });
      expect(list.status(), await list.text()).toBe(200);
      const listBody = await list.json();
      expect((listBody.documents || []).some((doc: { id: string; original_filename: string }) => doc.id === docId && doc.original_filename === fileName)).toBe(true);

      const detail = await request.get(`${API_BASE}/api/documents/${docId}`, {
        headers: { Authorization: `Bearer ${businessToken}` },
      });
      expect(detail.status(), await detail.text()).toBe(200);
      const detailBody = await detail.json();
      expect(detailBody.id).toBe(docId);
      expect(detailBody.original_filename).toBe(fileName);

      const file = await request.get(`${API_BASE}/api/documents/${docId}/file`, {
        headers: { Authorization: `Bearer ${businessToken}` },
      });
      expect(file.status(), await file.text()).toBe(200);
      expect(await file.text()).toContain("AMINRA document live UAT sample");
    } finally {
      const del = await request.delete(`${API_BASE}/api/documents/${docId}`, {
        headers: { Authorization: `Bearer ${businessToken}` },
      });
      expect([200, 404]).toContain(del.status());
    }
  });
});
