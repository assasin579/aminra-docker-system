/**
 * Chat (submission_comments) feature removal — 2026-04-26.
 *
 * User decision: chat workflow redundant with `/request-revision` flow which
 * carries per-doc severity feedback + structured audit trail.
 *
 * Regression gates:
 *   - Backend `/comments` endpoints return 404
 *   - OpenAPI no longer advertises any /comments path
 *   - FE submissions page has no comment thread UI / state
 *   - DB schema `submission_comments` left dormant for rollback (verify table
 *     still exists but app code never touches it)
 */
import { test, expect } from "@playwright/test";

test.describe("chat removed (submission_comments)", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "removal regression only needs desktop coverage",
    );
  });

  test("backend /comments endpoints return 404", async ({ request }) => {
    const login = await request.post("/api/auth/login", {
      data: { email: "cb-demo@demo.aminra.vn", password: "DemoP@ss2026", role: "provider" },
    });
    if (!login.ok()) test.skip(true, "cb-demo not seeded");
    const { access_token } = await login.json();

    const stub = "00000000-0000-0000-0000-000000000000";
    const get  = await request.get(`/api/api/submissions/received/${stub}/comments`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const post = await request.post(`/api/api/submissions/received/${stub}/comments`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { message: "test" },
    });
    expect(get.status(), "GET /comments must be 404").toBe(404);
    expect(post.status(), "POST /comments must be 404").toBe(404);
  });

  test("OpenAPI advertises no /comments paths", async ({ request }) => {
    const r = await request.get("/api/openapi.json");
    expect(r.ok()).toBeTruthy();
    const schema = await r.json();
    const paths = Object.keys(schema?.paths ?? {});
    const commentPaths = paths.filter(p => p.endsWith("/comments"));
    expect(commentPaths, "no /comments endpoints should remain").toEqual([]);
  });

  test("FE submissions page has no chat UI / state references", async () => {
    const { readFile } = await import("node:fs/promises");
    const src = await readFile("app/submissions/page.tsx", "utf8");
    // No comment-related UI/state should remain
    expect(src, "Comment interface removed").not.toMatch(/interface Comment\b/);
    expect(src, "loadingComments state removed").not.toContain("loadingComments");
    expect(src, "newComment state removed").not.toContain("newComment");
    expect(src, "sendComment handler removed").not.toContain("sendComment");
    expect(src, "Trao đổi heading removed").not.toContain("Trao đổi");
    expect(src, "comment fetch in toggleExpand removed").not.toMatch(/\/received\/\$\{[^}]+\}\/comments/);
  });
});
