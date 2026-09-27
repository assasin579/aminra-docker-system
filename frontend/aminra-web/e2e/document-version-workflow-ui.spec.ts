import { expect, test } from "@playwright/test";
import path from "node:path";

const EVIDENCE_DIR = process.env.DOC_VERSION_EVIDENCE_DIR ||
  path.resolve(process.cwd(), "../../docs/qa/2026-09-26-document-version-workflow/screenshots");

const oldDoc = {
  id: "11111111-1111-4111-8111-111111111111",
  original_filename: "approved-v1-halal-policy.txt",
  doc_type: "halal_policy",
  doc_type_label: "Halal Policy",
  compliance_score: 92,
  overall_status: "compliant",
  file_size: 128,
  uploaded_by_name: "Version Owner",
  uploaded_at: "2026-09-26T08:00:00Z",
  revision_count: 1,
  status: null,
  approval_status: "approved",
  version_number: 1,
};

const newDocId = "22222222-2222-4222-8222-222222222222";

const businessProfile = {
  id: "version-business-user",
  email: "version@aminra.test",
  role: "business",
  status: "active",
  company_name: "AMINRA Version Evidence Co",
  company_code: "VER",
  is_owner: true,
  tenant_id: "version-tenant",
  permissions: {
    can_edit: true,
    can_delete: true,
    can_approve: true,
    can_upload: true,
    can_approve_documents: true,
  },
  ihc_role: null,
};

async function bootVersioningPage(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(businessProfile) });
  });
  await page.route("**/api/api/feature-flags/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ tenant_id: businessProfile.tenant_id, flags: { document_versioning_v1: true } }),
    });
  });
  await page.route("**/api/api/official-artifacts", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ artifacts: [], total: 0 }) });
  });
  await page.context().route("**/api/api/documents/**/versions**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        doc_id: oldDoc.id,
        max_depth: 10,
        versions: [
          { id: oldDoc.id, version_number: 1, approval_status: "obsolete", approved_at: "2026-09-26T08:00:00Z", effective_date: "2026-09-26" },
          { id: newDocId, version_number: 2, approval_status: "approved", approved_at: "2026-09-26T09:00:00Z", effective_date: "2026-09-26" },
        ],
      }),
    });
  });
  await page.route(`**/api/api/documents/${oldDoc.id}/supersede`, async (route) => {
    expect(route.request().method()).toBe("POST");
    const body = JSON.parse(route.request().postData() || "{}");
    expect(body.new_document_id).toBe(newDocId);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ message: "Đã thay thế phiên bản", old_document_id: oldDoc.id, new_document_id: newDocId, new_version_number: 2 }),
    });
  });
  await page.route(/\/api\/api\/documents\?.*$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ documents: [oldDoc], total: 1, page: 1, page_size: 15 }),
    });
  });
  await page.addInitScript((profile) => {
    window.localStorage.setItem("aminra_user_token", "version-token");
    window.localStorage.setItem("aminra_user_profile", JSON.stringify(profile));
    document.cookie = "aminra_session=1; path=/; max-age=31536000; SameSite=Lax";
  }, businessProfile);
  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Tài liệu" })).toBeVisible();
  await expect(page.getByText(oldDoc.original_filename)).toBeVisible();
}

test.describe("document version workflow UI", () => {
  test("shows /versions chain and submits supersede action", async ({ page }) => {
    await bootVersioningPage(page);

    const versionResponsePromise = page.waitForResponse((response) =>
      response.url().includes(`/api/api/documents/${oldDoc.id}/versions`),
    );
    await page.getByRole("button", { name: "v1", exact: true }).click();
    const versionResponse = await versionResponsePromise;
    expect(versionResponse.status(), `version chain request ${versionResponse.url()}`).toBe(200);
    await expect(page.getByRole("heading", { name: "Chuỗi phiên bản" })).toBeVisible();
    await expect(page.getByText(`${oldDoc.id}`)).toBeVisible();
    await expect(page.getByText(newDocId)).toBeVisible();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "version-chain.png"), fullPage: true });
    await page.getByRole("button", { name: "✕" }).click();

    await page.getByRole("button", { name: "Thay thế" }).click();
    await expect(page.getByRole("heading", { name: "Thay thế phiên bản" })).toBeVisible();
    await page.getByPlaceholder("UUID tài liệu mới").fill(newDocId);
    await page.getByRole("button", { name: "Xác nhận thay thế" }).click();
    await expect(page.getByRole("heading", { name: "Thay thế phiên bản" })).toBeHidden();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "supersede-action.png"), fullPage: true });
  });
});
