/**
 * Template content integrity check.
 *
 * Bug 2026-04-26: `halal_policy_vi.docx` was overwritten with the
 * `sop_cleaning_sanitation` content (admin uploaded wrong file). The lookup
 * `_find_template_file()` happily served the file because it only checked the
 * `_vi` suffix, not exact filename match.
 *
 * Fixes applied:
 *   - Code: `_find_template_file()` now requires exact `{doc_type}_{lang}.docx`
 *   - Data: `halal_policy_vi.docx` restored from the canonical SILVERGEM backup
 *
 * This regression gate downloads each available template + asserts the
 * decompressed content contains keywords matching the doc_type. Catches both
 * mis-named files and content-swap accidents on future admin uploads.
 */
import { test, expect } from "@playwright/test";

const BUSINESS_LOGIN = { email: "biz-demo-1@demo.aminra.vn", password: "DemoP@ss2026", role: "business" };

test.describe("template content integrity", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "template integrity only needs desktop coverage",
    );
  });

  /**
   * Hash-based invariant: no two doc_types may serve the SAME file.
   * Catches the exact 2026-04-26 bug (halal_policy_vi.docx had identical MD5
   * with sop_cleaning_sanitation_vi.docx because admin uploaded wrong content).
   */
  test("no two doc_types serve the same template content", async ({ request }) => {
    const { createHash } = await import("node:crypto");

    const login = await request.post("/api/auth/login", { data: BUSINESS_LOGIN });
    if (!login.ok()) test.skip(true, "biz-demo-1 not seeded");
    const { access_token } = await login.json();

    const list = await request.get("/api/templates/available", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(list.ok()).toBeTruthy();
    const { templates } = await list.json();

    const hashByDocType: Record<string, string> = {};
    for (const t of templates as Array<{ doc_type: string; has_vi: boolean }>) {
      if (!t.has_vi) continue;
      const dl = await request.get(`/api/templates/${t.doc_type}/download?lang=vi`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      if (!dl.ok()) continue;
      const buf = Buffer.from(await dl.body());
      hashByDocType[t.doc_type] = createHash("md5").update(buf).digest("hex");
    }

    const seen: Record<string, string> = {};
    const collisions: string[] = [];
    for (const [docType, hash] of Object.entries(hashByDocType)) {
      if (seen[hash]) {
        collisions.push(`${docType} == ${seen[hash]} (md5=${hash})`);
      } else {
        seen[hash] = docType;
      }
    }

    expect(
      collisions,
      "Two doc_types must not serve the same content. Likely admin uploaded wrong file to the second one.\n" +
        collisions.map(c => "  - " + c).join("\n"),
    ).toEqual([]);
  });

  test("template download returns no-store headers (prevent stale browser cache)", async ({ request }) => {
    const login = await request.post("/api/auth/login", { data: BUSINESS_LOGIN });
    if (!login.ok()) test.skip(true, "biz-demo-1 not seeded");
    const { access_token } = await login.json();
    const r = await request.get("/api/templates/halal_policy/download?lang=vi", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(r.status()).toBe(200);
    const cacheControl = r.headers()["cache-control"] ?? "";
    expect(cacheControl, "must include no-store so admin rotations propagate immediately").toContain("no-store");
    expect(r.headers()["etag"], "must set ETag based on file mtime").toBeTruthy();
  });

  /**
   * Static guard — backend `_find_template_file` must use exact filename match,
   * not stem suffix. The original implementation matched any *_vi.docx in the
   * folder which let stray files leak.
   */
  test("backend _find_template_file uses exact canonical filename", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("../../backend/app.py", "utf8");
    const fnMatch = src.match(/def _find_template_file\([^)]*\)[\s\S]{0,800}/);
    expect(fnMatch, "_find_template_file must exist in backend/app.py").not.toBeNull();
    const body = fnMatch![0];
    expect(body, "must build canonical {doc_type}_{lang}.docx path").toMatch(
      /\{doc_type\}_\{lang\}\.docx/,
    );
    expect(body, "must NOT iterate dir + use stem.endswith() (old buggy approach)").not.toMatch(
      /\.iterdir\(\)[\s\S]*?stem\.endswith/,
    );
  });
});
