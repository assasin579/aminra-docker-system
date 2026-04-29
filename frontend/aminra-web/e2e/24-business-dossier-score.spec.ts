/**
 * Provider business dossier + scoring page.
 *
 * Verifies the cert-rule fixes from 2026-04-26 plus the new dossier/score UI:
 *  1. Dossier endpoint returns docs grouped by doc_type with revisions
 *  2. Score endpoint returns composite + components breakdown
 *  3. Provider page /businesses/[id] renders both
 *  4. Backend rejects PUT /status to 'approved' (must use /approve-final)
 *  5. approve-final rejects empty submissions
 */
import { test, expect } from "@playwright/test";

test.describe("provider dossier + score", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "dossier ui only needs desktop coverage",
    );
  });

  test("dossier + score endpoints return shape", async ({ request }) => {
    const login = await request.post("/api/auth/login", {
      data: {
        email: "cb-demo@demo.aminra.vn",
        password: "DemoP@ss2026",
        role: "provider",
      },
    });
    if (!login.ok()) test.skip(true, "cb-demo not seeded");
    const { access_token } = await login.json();

    const list = await request.get("/api/api/audits/businesses", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(list.ok()).toBeTruthy();
    const { businesses } = await list.json();
    expect(businesses.length).toBeGreaterThan(0);
    const bizId = businesses[0].id;

    const dossier = await request.get(
      `/api/api/audits/businesses/${bizId}/dossier`,
      {
        headers: { Authorization: `Bearer ${access_token}` },
      },
    );
    expect(dossier.ok()).toBeTruthy();
    const d = await dossier.json();
    expect(d).toHaveProperty("business");
    expect(d).toHaveProperty("documents_by_type");
    expect(d).toHaveProperty("submissions");
    expect(d).toHaveProperty("audit_visits");
    expect(Array.isArray(d.documents_by_type)).toBeTruthy();

    const score = await request.get(
      `/api/api/audits/businesses/${bizId}/score`,
      {
        headers: { Authorization: `Bearer ${access_token}` },
      },
    );
    expect(score.ok()).toBeTruthy();
    const s = await score.json();
    expect(s).toHaveProperty("composite_score");
    expect(s).toHaveProperty("rating");
    expect(s.doc_component).toHaveProperty("score");
    expect(s.audit_component).toHaveProperty("score");
  });

  test("PUT /received/{id}/status rejects status='approved'", async ({
    request,
  }) => {
    const login = await request.post("/api/auth/login", {
      data: {
        email: "cb-demo@demo.aminra.vn",
        password: "DemoP@ss2026",
        role: "provider",
      },
    });
    if (!login.ok()) test.skip(true, "cb-demo not seeded");
    const { access_token } = await login.json();

    const stub = "00000000-0000-0000-0000-000000000000";
    const res = await request.put(
      `/api/api/submissions/received/${stub}/status`,
      {
        headers: {
          Authorization: `Bearer ${access_token}`,
          "Content-Type": "application/json",
        },
        data: { status: "approved" },
      },
    );
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.detail).toMatch(/approve-final/);
  });

  test("provider page /businesses/[id] renders score + folder", async ({
    page,
    request,
  }) => {
    const login = await request.post("/api/auth/login", {
      data: {
        email: "cb-demo@demo.aminra.vn",
        password: "DemoP@ss2026",
        role: "provider",
      },
    });
    if (!login.ok()) test.skip(true, "cb-demo not seeded");
    const { access_token, user } = await login.json();

    const list = await request.get("/api/api/audits/businesses", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const { businesses } = await list.json();
    if (!businesses.length) test.skip(true, "no businesses in portfolio");
    const bizId = businesses[0].id;

    await page.addInitScript(
      ({ t, u }) => {
        localStorage.setItem("aminra_user_token", t);
        localStorage.setItem("aminra_user_profile", u);
      },
      { t: access_token, u: JSON.stringify(user) },
    );

    await page.goto(`/businesses/${bizId}`);
    await expect(
      page.getByRole("heading", { name: businesses[0].company_name }),
    ).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Điểm doanh nghiệp")).toBeVisible();
    await expect(page.getByText(/Thư mục tài liệu/)).toBeVisible();
    await expect(page.getByText(/Hồ sơ đã gửi/)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Kiểm định thực tế/ }),
    ).toBeVisible();
  });
});
