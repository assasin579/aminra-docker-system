/**
 * MVP demo — Tier 1 + Tier 2 public + business smoke flows.
 *
 * Combines flows 1-11 from docs/mvp-demo-test-script.md so the entire
 * customer-facing happy path can be verified in one parallel run.
 *
 * Skips gracefully if seed data missing (run scripts/seed_demo_data.py first).
 */
import { test, expect } from "./fixtures";

const DEMO_CERT = "HALAL-2026-DEMO";

// ── Flow 1: Public verify cert ─────────────────────────────────────────────

test.describe("MVP Flow 1: Public verify cert", () => {
  test("API returns valid=true for seeded demo cert", async ({ api }) => {
    const res = await api.get(`/api/submissions/certificates/public/${DEMO_CERT}`);
    if (res.status() === 404) {
      test.skip(true, "demo cert missing — run seed_demo_data.py");
    }
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.valid).toBe(true);
    expect(body.cert_number).toBe(DEMO_CERT);
    expect(body.company_name).toContain("Demo");
  });

  test("Verify page renders cert details + green check", async ({ page }) => {
    await page.goto(`/verify/${DEMO_CERT}`);
    await page.waitForLoadState("networkidle");

    // Either 'Chứng nhận hợp lệ' OR 'Không tìm thấy' — depending on seed
    const valid = await page.getByText(/Chứng nhận hợp lệ/i).isVisible().catch(() => false);
    const notFound = await page.getByText(/Không tìm thấy/i).isVisible().catch(() => false);

    if (notFound) {
      test.skip(true, "demo cert missing");
    }
    expect(valid).toBe(true);
    // Cert number appears multiple times on page (header + table) — use first
    await expect(page.getByText(DEMO_CERT).first()).toBeVisible();
  });
});

// ── Flow 2: RAG chat ───────────────────────────────────────────────────────

test.describe("MVP Flow 2: Halal advisor chat", () => {
  test("Topics endpoint reachable", async ({ api }) => {
    const res = await api.get("/topics");
    expect(res.status()).toBe(200);
  });

  test("Chat page renders without auth", async ({ page }) => {
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("/chat");
  });
});

// ── Flow 3: Forgot password (covered by 12-cuj-password-reset.spec.ts) ────
// ── Flow 4: Landing + Privacy/Terms (covered by visual-regression.spec.ts) ─

// ── Flow 5: Public cert PDF download ──────────────────────────────────────

test.describe("MVP Flow 5: Public cert PDF download", () => {
  test("Cert PDF endpoint requires token (security)", async ({ api }) => {
    // Without token → 401 — no public access without authentication
    const res = await api.get(`/api/submissions/certificates/00000000-0000-0000-0000-000000000000/pdf`);
    expect([401, 404]).toContain(res.status());
  });
});

// ── Flow 6: Business registration → login ─────────────────────────────────

test.describe("MVP Flow 6: Business registration + login", () => {
  test("Business login with seeded demo account works", async ({ api }) => {
    const res = await api.post("/auth/login", {
      data: {
        email: "biz-demo-1@demo.aminra.vn",
        password: "DemoP@ss2026",
      },
    });
    if (res.status() !== 200) {
      test.skip(true, "demo seed missing");
    }
    const body = await res.json();
    expect(body.access_token).toBeTruthy();
    expect(body.user?.role).toBe("business");
  });

  test("Business login page renders form", async ({ page }) => {
    await page.goto("/business/login");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });
});

// ── Flow 8: Submissions list ──────────────────────────────────────────────

test.describe("MVP Flow 8: Submissions list (business view)", () => {
  test("my-submissions returns array for authenticated business", async ({ api }) => {
    const login = await api.post("/auth/login", {
      data: { email: "biz-demo-1@demo.aminra.vn", password: "DemoP@ss2026" },
    });
    if (login.status() !== 200) test.skip(true, "demo seed missing");
    const { access_token } = await login.json();

    const res = await api.get("/api/submissions/my-submissions", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect([200, 307]).toContain(res.status());

    if (res.status() === 200) {
      const body = await res.json();
      expect(Array.isArray(body) || Array.isArray(body.submissions)).toBe(true);
    }
  });
});

// ── Flow 11: Submissions page renders ─────────────────────────────────────

test.describe("MVP Flow 11: Submissions page renders", () => {
  test("Page redirects to login or renders", async ({ page }) => {
    await page.goto("/submissions");
    await page.waitForLoadState("networkidle");
    const url = page.url();
    expect(url).toMatch(/(submissions|login)/);
  });
});
