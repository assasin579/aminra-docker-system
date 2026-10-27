import { expect, test } from "@playwright/test";

// API-mocked acceptance requires Playwright to intercept requests before the app's
// PWA service worker can serve or proxy them. This test is not full-stack E2E.
test.use({ serviceWorkers: "block" });

const profile = {
  id: "synthetic-owner", email: "g1@example.invalid", role: "business", status: "active",
  company_name: "Synthetic G1", company_code: "G1", is_owner: true,
  tenant_id: "tenant-synthetic", industry_schema_id: "industry-synthetic",
};
const stats = { total_documents: 2, avg_score: 74, member_count: 1, doc_type_progress: [], recent_activity: [] };
const dossierDashboard = {
  schema_version: "1.0", state: "ready", as_of: "2026-10-26T00:00:00Z", page: 1, page_size: 20, total_dossiers: 2,
  profiles: [{ id: "standard-a", code: "HALAL", name_vi: "Halal", dossiers: [{
    id: "dossier-a", title: "Synthetic dossier", status: "in_progress", requirements_version_id: "version-a",
    requirements_binding_status: "bound", updated_at: "2026-10-26T00:00:00Z",
    readiness: { state: "requirements_pending", readiness_percent: 50, requirements_binding_status: "bound", requirements_version_id: "version-a", next_action: "upload_required_documents", next_actor_role: "business", requirement_slots: [{ doc_type: "manual", required: true, state: "missing_required", requirements_version_id: "version-a" }] },
  }] }],
};

test("business G1 dashboard renders integrated version-bound readiness without legacy denominator", async ({ page }) => {
  const requests: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript((user) => {
    const encode = (value: unknown) => btoa(JSON.stringify(value)).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
    const payload = encode({ email: user.email, exp: Math.floor(Date.now() / 1000) + 7200 });
    localStorage.setItem("aminra_user_token", `e30.${payload}.synthetic-signature`);
    localStorage.setItem("aminra_user_profile", JSON.stringify(user));
  }, profile);
  await page.context().route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    requests.push(path);
    const data: Record<string, unknown> = {
      "/api/auth/me": profile,
      "/api/api/dashboard/stats": stats,
      "/api/api/submissions/cert-timeline": { certificates: [] },
      "/api/dossiers/dashboard": dossierDashboard,
    };
    if (!(path in data)) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "unexpected synthetic request" }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data[path]) });
  });
  await page.goto("/dashboard/business");
  await expect(page.getByRole("heading", { name: "Profile readiness" })).toBeVisible();
  await expect(page.getByText("Synthetic dossier")).toBeVisible();
  await expect(page.getByText(/requirements version: version-a/i)).toBeVisible();
  await expect(page.getByText(/Readiness: 50%/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /upload required documents/i })).toHaveAttribute("href", "/dossiers/dossier-a");
  await expect(page.locator('[data-dashboard-section="readiness-hero"]')).toHaveCount(0);
  await expect(page.getByText(/13/)).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Tài liệu", exact: true })).toBeVisible();
  await expect(page.getByText("Showing 1 dossiers on this page (page-scoped); 2 total.")).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.locator('[aria-label="Profile readiness"]').evaluate((el) => el.getBoundingClientRect().width)).toBeLessThanOrEqual(375);
  const drilldown = page.getByRole("link", { name: /upload required documents/i });
  await drilldown.focus();
  await expect(drilldown).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/dossiers\/dossier-a$/);
  expect(requests).toContain("/api/dossiers/dashboard");
  expect(errors).toEqual([]);
});

test("synthetic browser covers loading, legacy UNKNOWN, optional-only, scope switch and late response", async ({ page }) => {
  const tenantA = { ...profile, id: "actor-a", tenant_id: "tenant-a" };
  const tenantB = { ...profile, id: "actor-b", tenant_id: "tenant-b" };
  const staleA = { ...dossierDashboard, profiles: [{ id: "p-a", code: "A", name_vi: "Profile A", dossiers: [{ ...dossierDashboard.profiles[0].dossiers[0], title: "Tenant A stale dossier" }] }] };
  const currentB = {
    ...dossierDashboard,
    total_dossiers: 8,
    profiles: [{ id: "p-b", code: "B", name_vi: "Profile B", dossiers: [
      { id: "legacy-b", title: "Tenant B legacy dossier", status: "in_progress", requirements_binding_status: "unknown", readiness: { state: "unknown", requirements_binding_status: "unknown", readiness_percent: null, requirement_slots: [] } },
      { id: "optional-b", title: "Tenant B optional-only dossier", status: "in_progress", requirements_version_id: "version-b", requirements_binding_status: "bound", readiness: { state: "requirements_no_required_slots", readiness_percent: null, requirements_binding_status: "bound", requirements_version_id: "version-b", next_action: "configure_required_slots", next_actor_role: "platform_admin", requirement_slots: [{ doc_type: "optional-policy", required: false, state: "optional_missing", requirements_version_id: "version-b" }] } },
    ] }],
  };
  let activeProfile = tenantA;
  let activeDashboard: Record<string, unknown> = staleA;
  let failDashboard = false;
  let holdFirst = true;
  let releaseFirst!: () => void;
  let firstRequestStarted!: () => void;
  const firstGate = new Promise<void>((resolve) => { releaseFirst = resolve; });
  const firstStarted = new Promise<void>((resolve) => { firstRequestStarted = resolve; });
  await page.addInitScript((user) => {
    if (localStorage.getItem("__g1_synthetic_auth_seeded") === "true") return;
    const encode = (value: unknown) => btoa(JSON.stringify(value)).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
    const payload = encode({ sub: user.id, email: user.email, exp: Math.floor(Date.now() / 1000) + 7200 });
    localStorage.setItem("aminra_user_token", `e30.${payload}.synthetic-signature`);
    localStorage.setItem("aminra_user_profile", JSON.stringify(user));
    localStorage.setItem("__g1_synthetic_auth_seeded", "true");
  }, tenantA);
  const tokenSubject = (route: import("@playwright/test").Route): string | null => {
    const token = route.request().headers()["authorization"]?.replace(/^Bearer\s+/i, "");
    const payload = token?.split(".")[1];
    if (!payload) return null;
    try { return JSON.parse(Buffer.from(payload, "base64url").toString("utf8")).sub ?? null; } catch { return null; }
  };
  let oldResponseAttempted = false;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/dossiers/dashboard") {
      if (tokenSubject(route) !== activeProfile.id) {
        return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "synthetic actor/token mismatch" }) });
      }
      if (activeProfile.id === tenantA.id && holdFirst) {
        firstRequestStarted();
        await firstGate;
        oldResponseAttempted = true;
        try { await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(staleA) }); } catch { /* old document request was aborted during auth-context reload */ }
        return;
      }
      if (failDashboard) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "synthetic unavailable" }) });
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(activeDashboard) });
    }
    const data: Record<string, unknown> = {
      "/api/auth/me": activeProfile,
      "/api/api/dashboard/stats": stats,
      "/api/api/submissions/cert-timeline": { certificates: [] },
    };
    if (path === "/api/auth/me" && tokenSubject(route) !== activeProfile.id) {
      return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "synthetic actor/token mismatch" }) });
    }
    if (!(path in data)) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "unexpected synthetic request" }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data[path]) });
  });
  await page.goto("/dashboard/business");
  await firstStarted;
  await expect(page.getByRole("status")).toContainText("Loading Profile readiness");

  activeProfile = tenantB;
  activeDashboard = currentB;
  holdFirst = false;
  await page.evaluate((user) => {
    const encode = (value: unknown) => btoa(JSON.stringify(value)).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
    const payload = encode({ sub: user.id, email: user.email, exp: Math.floor(Date.now() / 1000) + 7200 });
    localStorage.setItem("aminra_user_token", `e30.${payload}.synthetic-signature`);
    localStorage.setItem("aminra_user_profile", JSON.stringify(user));
  }, tenantB);
  // Reinitialize the actual UserAuthProvider with a new synthetic actor/token.
  // The component-level deferred-fetch test separately proves the same-mounted
  // context-generation guard (reload itself aborts the old document request).
  await page.reload();
  await expect(page.getByText("Tenant B legacy dossier")).toBeVisible();
  await expect(page.getByText("UNKNOWN (legacy/unbound)")).toBeVisible();
  await expect(page.getByText("Tenant B optional-only dossier")).toBeVisible();
  await expect(page.getByText("Published requirements contain no required slots; percentage is not applicable.")).toBeVisible();
  await expect(page.getByText("Showing 2 dossiers on this page (page-scoped); 8 total.")).toBeVisible();
  releaseFirst();
  await expect.poll(() => oldResponseAttempted).toBe(true);
  await expect(page.getByText("Tenant A stale dossier")).toHaveCount(0);

  failDashboard = true;
  await page.reload();
  await expect(page.getByText("Could not load Profile readiness. Please try again.", { exact: true })).toBeVisible();
});
