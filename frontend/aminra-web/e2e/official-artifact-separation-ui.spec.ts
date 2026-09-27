import { expect, test } from "@playwright/test";
import path from "node:path";

const EVIDENCE_DIR = process.env.OFFICIAL_ARTIFACT_EVIDENCE_DIR ||
  path.resolve(process.cwd(), "../../docs/qa/2026-09-26-official-artifact-separation/screenshots");

const businessProfile = {
  id: "official-artifact-business-user",
  email: "official-artifact@aminra.test",
  role: "business",
  status: "active",
  company_name: "AMINRA Official Artifact Evidence Co",
  company_code: "OFFICIAL",
  is_owner: true,
  tenant_id: "official-artifact-tenant",
  permissions: {
    can_edit: true,
    can_delete: true,
    can_approve: true,
    can_upload: true,
    can_approve_documents: true,
  },
  ihc_role: null,
};

const officialArtifact = {
  id: "33333333-3333-4333-8333-333333333333",
  source_document_id: "11111111-1111-4111-8111-111111111111",
  artifact_kind: "approved_document",
  original_filename: "official-halal-policy.pdf",
  file_size: 4096,
  mime_type: "application/pdf",
  sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  approved_by_user_id: "22222222-2222-4222-8222-222222222222",
  approved_at: "2026-09-26T09:30:00Z",
  effective_date: "2026-09-26",
  next_review_date: "2027-09-26",
  retention_expires_at: "2031-09-26T00:00:00Z",
  created_at: "2026-09-26T09:31:00Z",
};

async function bootDocumentsPage(page: import("@playwright/test").Page) {
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
  await page.context().route(/\/api\/api\/documents\?.*$/, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ documents: [], total: 0, page: 1, page_size: 15 }) });
  });
  await page.context().route(/\/api\/api\/official-artifacts(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ artifacts: [officialArtifact], total: 1 }),
    });
  });
  await page.addInitScript((profile) => {
    window.localStorage.setItem("aminra_user_token", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJwbGF5d3JpZ2h0LW1vY2siLCJlbWFpbCI6InB3QGFtaW5yYS50ZXN0In0.c2ln");
    window.localStorage.setItem("aminra_user_profile", JSON.stringify(profile));
    document.cookie = "aminra_session=1; path=/; max-age=31536000; SameSite=Lax";
  }, businessProfile);
  const officialResponsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/api/official-artifacts"),
  );
  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Tài liệu" })).toBeVisible();
  const officialResponse = await officialResponsePromise;
  expect(officialResponse.status(), `official artifacts request ${officialResponse.url()}`).toBe(200);
}

test.describe("official artifact separation UI", () => {
  test("renders official artifacts as read-only separate tab", async ({ page }) => {
    await bootDocumentsPage(page);
    await page.getByRole("tab", { name: "Bản chính thức" }).click();

    await expect(page.getByText("official-halal-policy.pdf")).toBeVisible();
    await expect(page.getByText("Bản chính thức").last()).toBeVisible();
    await expect(page.getByText("aaaaaaaaaaaa")).toBeVisible();
    await expect(page.getByRole("button", { name: "Tải xuống" })).toBeVisible();

    await expect(page.getByRole("button", { name: "Xoá" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Đánh giá" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Thay thế" })).toHaveCount(0);

    await page.screenshot({ path: path.join(EVIDENCE_DIR, "official-artifacts-read-only.png"), fullPage: true });
  });
});
