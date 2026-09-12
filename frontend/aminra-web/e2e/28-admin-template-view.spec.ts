/**
 * Admin file preview endpoints — view template/reference DOCX in-browser.
 *
 * Added 2026-04-26 after the halal_policy mis-upload bug exposed that admin
 * couldn't verify uploaded content without re-downloading. New endpoints:
 *   GET /admin/templates/{doc_type}/template-file/view?lang=vi&token=...
 *   GET /admin/templates/{doc_type}/files/{filename}/view?lang=vi&token=...
 *
 * Both accept Bearer header OR `?token=` query (so "open in new tab" works
 * since browsers don't carry custom headers on direct nav).
 */
import { test, expect } from "@playwright/test";
import { requireAdminToken } from "./helpers/admin-token";

test.describe("admin file preview", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "preview endpoints only need desktop coverage",
    );
  });

  test("view DOCX template returns PDF for inline preview (LibreOffice conversion)", async ({
    request,
  }) => {
    const token = await requireAdminToken(request);

    const r = await request.get(
      "/api/admin/templates/halal_policy/template-file/view?lang=vi",
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    expect(r.status()).toBe(200);
    const ct = r.headers()["content-type"] ?? "";
    expect(
      ct,
      "DOCX must be converted to PDF for in-browser preview",
    ).toContain("application/pdf");
    const cd = r.headers()["content-disposition"] ?? "";
    expect(cd).toMatch(/inline/);

    // Verify response body is a real PDF (magic bytes %PDF)
    const body = await r.body();
    expect(body.subarray(0, 4).toString()).toBe("%PDF");
  });

  test("view template-file via query-string token (for new-tab UX)", async ({
    request,
  }) => {
    const token = await requireAdminToken(request);

    const r = await request.get(
      `/api/admin/templates/halal_policy/template-file/view?lang=vi&token=${encodeURIComponent(token)}`,
    );
    expect(r.status()).toBe(200);
    const body = await r.body();
    expect(body.subarray(0, 4).toString()).toBe("%PDF");
  });

  test("repeated PDF requests return identical content (cache deterministic)", async ({
    request,
  }) => {
    const token = await requireAdminToken(request);
    const url = `/api/admin/templates/halal_policy/template-file/view?lang=vi&token=${encodeURIComponent(token)}`;

    const r1 = await request.get(url);
    const r2 = await request.get(url);
    expect(r1.status()).toBe(200);
    expect(r2.status()).toBe(200);
    const b1 = await r1.body();
    const b2 = await r2.body();
    expect(b1.length).toBe(b2.length);
    expect(b1.equals(b2)).toBe(true);
  });

  test("view rejects missing/garbage auth", async ({ request }) => {
    expect(
      (
        await request.get(
          "/api/admin/templates/halal_policy/template-file/view?lang=vi",
        )
      ).status(),
    ).toBe(401);
    expect(
      (
        await request.get(
          "/api/admin/templates/halal_policy/template-file/view?lang=vi&token=garbage123",
        )
      ).status(),
    ).toBe(401);
  });

  test("view rejects path-traversal in filename", async ({ request }) => {
    const token = await requireAdminToken(request);

    // Backend should sanitize the filename — `..%2F` in path should not escape
    const r = await request.get(
      `/api/admin/templates/halal_policy/files/..%2F..%2Fapp.py/view?lang=vi&token=${encodeURIComponent(token)}`,
    );
    expect([400, 404]).toContain(r.status());
  });
});
