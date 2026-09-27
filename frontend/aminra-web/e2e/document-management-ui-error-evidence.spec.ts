import { expect, test } from "@playwright/test";
import path from "node:path";

const EVIDENCE_DIR = process.env.DOC_UI_ERROR_EVIDENCE_DIR ||
  path.resolve(process.cwd(), "../../docs/qa/2026-09-26-document-management-ui-error/screenshots");

const businessProfile = {
  id: "ui-error-business-user",
  email: "ui-error@aminra.test",
  role: "business",
  status: "active",
  company_name: "AMINRA UI Error Evidence Co",
  company_code: "UIERR",
  is_owner: true,
  tenant_id: "ui-error-tenant",
  permissions: {
    can_edit: true,
    can_delete: true,
    can_approve: true,
    can_upload: true,
    can_approve_documents: true,
  },
  ihc_role: null,
};

function alertWithText(page: import("@playwright/test").Page, text: string) {
  return page.locator('[role="alert"]').filter({ hasText: text });
}

const sampleDoc = {
  id: "11111111-1111-4111-8111-111111111111",
  original_filename: "ui-error-evidence-halal-policy.txt",
  doc_type: "halal_policy",
  doc_type_label: "Halal Policy",
  compliance_score: null,
  overall_status: null,
  file_size: 128,
  uploaded_by_name: "UI Error Owner",
  uploaded_at: "2026-09-26T08:00:00Z",
  revision_count: 1,
  status: null,
};

async function bootDocumentsPage(page: import("@playwright/test").Page, options?: {
  listStatus?: number;
  listBody?: unknown;
  detailStatus?: number;
  detailBody?: unknown;
  deleteStatus?: number;
  deleteBody?: unknown;
  uploadStatus?: number;
  uploadBody?: unknown;
}) {
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(businessProfile) });
  });

  await page.context().route(/\/api\/api\/documents\?.*$/, async (route) => {
    const status = options?.listStatus ?? 200;
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(options?.listBody ?? (status >= 400 ? { detail: "Danh sách tài liệu tạm thời không khả dụng" } : { documents: [sampleDoc], total: 1 })),
    });
  });

  await page.context().route(new RegExp(`/api/api/documents/${sampleDoc.id}(?:\\?.*)?$`), async (route) => {
    if (route.request().method() === "DELETE") {
      const status = options?.deleteStatus ?? 200;
      await route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(options?.deleteBody ?? (status >= 400 ? { detail: "Không thể xoá tài liệu do lỗi kiểm thử" } : { ok: true })),
      });
      return;
    }
    const status = options?.detailStatus ?? 200;
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(options?.detailBody ?? (status >= 400 ? { detail: "Không tải được chi tiết tài liệu" } : sampleDoc)),
    });
  });

  await page.route("**/api/api/documents/upload", async (route) => {
    const status = options?.uploadStatus ?? 500;
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(options?.uploadBody ?? { detail: "Upload bị từ chối bởi kiểm thử UI" }),
    });
  });

  await page.addInitScript((profile) => {
    window.localStorage.setItem("aminra_user_token", "ui-error-token");
    window.localStorage.setItem("aminra_user_profile", JSON.stringify(profile));
    document.cookie = "aminra_session=1; path=/; max-age=31536000; SameSite=Lax";
  }, businessProfile);

  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Tài liệu" })).toBeVisible();
}

test.describe("document management browser UI error evidence", () => {
  test("shows visible list error when document list API fails", async ({ page }) => {
    await bootDocumentsPage(page, { listStatus: 503 });
    await expect(alertWithText(page, "Danh sách tài liệu tạm thời không khả dụng")).toBeVisible();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "list-error.png"), fullPage: true });
  });

  test("shows visible detail error when document detail API fails", async ({ page }) => {
    await bootDocumentsPage(page, { detailStatus: 502 });
    await page.getByRole("button", { name: "Kết quả đánh giá" }).click();
    await expect(alertWithText(page, "Không tải được chi tiết tài liệu")).toBeVisible();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "detail-error.png"), fullPage: true });
  });

  test("shows delete error and keeps document visible when delete API fails", async ({ page }) => {
    await bootDocumentsPage(page, { deleteStatus: 409 });
    page.on("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Xoá" }).click();
    await expect(alertWithText(page, "Không thể xoá tài liệu do lỗi kiểm thử")).toBeVisible();
    await expect(page.getByText(sampleDoc.original_filename)).toBeVisible();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "delete-error.png"), fullPage: true });
  });

  test("shows upload API error inside upload modal", async ({ page }) => {
    await bootDocumentsPage(page, { uploadStatus: 422 });
    await page.getByRole("button", { name: "Upload tài liệu" }).first().click();
    await page.getByRole("button", { name: "Halal Policy" }).click();
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByText("Kéo thả file hoặc click để chọn").click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: "upload-error-evidence.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("upload failure evidence"),
    });
    await expect(alertWithText(page, "Upload bị từ chối bởi kiểm thử UI")).toBeVisible();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "upload-error.png"), fullPage: true });
  });
});
