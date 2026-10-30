import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";
import { requireKeycloakUserToken } from "./helpers/auth-token";

const API_BASE = (process.env.PW_API_BASE || "http://localhost:8100").replace(/\/$/, "");
const businessEmail = process.env.PW_BIZ_EMAIL || process.env.DEMO_BUSINESS_EMAIL || "biz-demo-1@demo.aminra.vn";
const businessPassword = process.env.PW_BIZ_PASSWORD || process.env.DEMO_PW;

function requireSecret(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing ${name}; source .qa/aminra-demo-credentials.env or run scripts/qa/repair-demo-accounts.sh`);
  }
  return value;
}

async function authGet(request: APIRequestContext, path: string, token: string) {
  return request.get(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${token}` } });
}

async function authPost(
  request: APIRequestContext,
  path: string,
  token: string,
  data?: Record<string, unknown>,
) {
  return request.post(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: data || {},
  });
}

test.describe("official artifact live API UAT", () => {
  test("approval creates immutable official artifact with download and source delete-block evidence", async ({ request }) => {
    const businessToken = await requireKeycloakUserToken(request, {
      email: businessEmail,
      password: requireSecret("PW_BIZ_PASSWORD", businessPassword),
    });

    const stamp = Date.now();
    const fileName = `official-artifact-live-uat-${stamp}.txt`;
    const content = `AMINRA official artifact live UAT ${stamp}`;

    const upload = await request.post(`${API_BASE}/api/documents/upload`, {
      headers: { Authorization: `Bearer ${businessToken}` },
      multipart: {
        doc_type: "halal_policy",
        file: {
          name: fileName,
          mimeType: "text/plain",
          buffer: Buffer.from(content),
        },
      },
    });
    expect(upload.status(), await upload.text()).toBe(200);
    const uploaded = await upload.json();
    const docId = uploaded.id as string;
    expect(docId).toMatch(/^[0-9a-f-]{36}$/i);

    const submit = await authPost(request, `/api/documents/${docId}/submit-for-approval`, businessToken);
    expect(submit.status(), await submit.text()).toBe(200);
    await expect(submit.json()).resolves.toMatchObject({ approval_status: "pending_approval" });

    const approve = await authPost(request, `/api/documents/${docId}/approve`, businessToken, {
      retention_period_days: 1825,
    });
    expect(approve.status(), await approve.text()).toBe(200);
    await expect(approve.json()).resolves.toMatchObject({ approval_status: "approved" });

    const artifacts = await authGet(request, `/api/official-artifacts?source_document_id=${docId}`, businessToken);
    expect(artifacts.status(), await artifacts.text()).toBe(200);
    const artifactBody = await artifacts.json();
    const artifact = (artifactBody.artifacts || []).find(
      (item: { source_document_id: string; original_filename: string; sha256: string }) =>
        item.source_document_id === docId && item.original_filename === fileName,
    );
    expect(artifact, JSON.stringify(artifactBody)).toBeTruthy();
    expect(artifact.sha256).toMatch(/^[0-9a-f]{64}$/);

    const artifactFile = await authGet(request, `/api/official-artifacts/${artifact.id}/file`, businessToken);
    expect(artifactFile.status(), await artifactFile.text()).toBe(200);
    expect(await artifactFile.text()).toContain(content);

    const deleteSource = await request.delete(`${API_BASE}/api/documents/${docId}`, {
      headers: { Authorization: `Bearer ${businessToken}` },
    });
    expect(deleteSource.status(), await deleteSource.text()).toBe(409);
    await expect(deleteSource.json()).resolves.toMatchObject({
      detail: expect.stringMatching(/bản chính thức|official/i),
    });
  });
});
