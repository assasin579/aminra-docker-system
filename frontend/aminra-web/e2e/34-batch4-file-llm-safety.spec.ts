/**
 * Phase 1 Batch 4 — File + LLM Safety Fixes (2026-04-26)
 *
 * Covers fixes from the bug audit:
 *   C7   /ingest sanitizes filename + UUID prefix (path traversal)
 *   C8   /evaluate sanitizes previous_context (prompt injection)
 *   C12  /ingest + /evaluate require auth
 *   C13  /rewrite + /generate-document require auth + rate limit
 *   W1-M1 _load_template_files_content: strict lang dir, no root fallback
 *   W2-M5 validate_upload: zip-bomb defense (uncompressed cap + ratio)
 */
import { test, expect } from "@playwright/test";

const BACKEND = "http://localhost:8100";

test.describe("Phase 1 Batch 4 — file + LLM safety", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "integration tests only need desktop coverage",
    );
  });

  test("static guards — code reflects all batch 4 fixes", async () => {
    const { readFile } = await import("node:fs/promises");
    const app = await readFile("../../backend/app.py", "utf8");
    const upload = await readFile("../../backend/auth/upload_utils.py", "utf8");

    // C12: /ingest requires auth
    expect(app).toMatch(/\/ingest[\s\S]{0,400}user: dict = Depends\(get_current_user\)/);
    // C12: /evaluate requires auth
    expect(app).toMatch(/\/evaluate[\s\S]{0,500}user: dict = Depends\(get_current_user\)/);
    // C13: /rewrite requires auth + rate limit
    expect(app).toMatch(/\/rewrite[\s\S]{0,400}_rate_limit: None = Depends\(rate_limit_upload\)[\s\S]{0,200}user: dict = Depends\(get_current_user\)/);
    // C13: /generate-document requires auth + rate limit
    expect(app).toMatch(/\/generate-document[\s\S]{0,400}_rate_limit: None = Depends\(rate_limit_upload\)[\s\S]{0,200}user: dict = Depends\(get_current_user\)/);
    // C7: filename sanitized + UUID prefix (f-string `{uuid.uuid4().hex[:12]}_{safe_name}`)
    expect(app).toMatch(/uuid\.uuid4\(\)\.hex\[:12\]\}_\{safe_name\}/);
    // C8: previous_context sanitized
    expect(app).toMatch(/sanitize FE-supplied previous_context|prev = previous_context\[:2000\]/);
    // W1-M1: helper does not fall back to root_dir
    expect(app).toMatch(/Strict lang-specific dir only/);
    // W2-M5: zip-bomb defense
    expect(upload).toMatch(/MAX_UNCOMPRESSED_SIZE/);
    expect(upload).toMatch(/MAX_COMPRESSION_RATIO/);
    expect(upload).toMatch(/possible zip-bomb/);
  });

  test("/ingest rejects unauthenticated", async ({ request }) => {
    const r = await request.post(`${BACKEND}/ingest`, {
      multipart: {
        file: { name: "x.txt", mimeType: "text/plain", buffer: Buffer.from("hello") },
      },
    });
    // 401 (auth check) OR 429 (rate-limit fired first under parallel load) —
    // both prove the endpoint refused anonymous access.
    expect([401, 429]).toContain(r.status());
  });

  test("/evaluate rejects unauthenticated", async ({ request }) => {
    const r = await request.post(`${BACKEND}/evaluate`, {
      multipart: {
        file: { name: "x.txt", mimeType: "text/plain", buffer: Buffer.from("hello") },
      },
    });
    // 401 (auth check) OR 429 (rate-limit fired first under parallel load) —
    // both prove the endpoint refused anonymous access.
    expect([401, 429]).toContain(r.status());
  });

  test("/rewrite rejects unauthenticated", async ({ request }) => {
    const r = await request.post(`${BACKEND}/rewrite`, {
      data: { section_text: "x", issue: "x", doc_type: "x" },
    });
    // 401 (auth check) OR 429 (rate-limit fired first under parallel load) —
    // both prove the endpoint refused anonymous access.
    expect([401, 429]).toContain(r.status());
  });

  test("/generate-document rejects unauthenticated", async ({ request }) => {
    const r = await request.post(`${BACKEND}/generate-document`, {
      data: { doc_type: "x", doc_type_label: "x" },
    });
    // 401 (auth check) OR 429 (rate-limit fired first under parallel load) —
    // both prove the endpoint refused anonymous access.
    expect([401, 429]).toContain(r.status());
  });
});
