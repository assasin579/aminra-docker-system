import { test, expect } from "./fixtures";

test.describe("04. Provider user workflow", () => {
  test("Provider can list received submissions", async ({ api, prov }) => {
    test.skip(!prov.token, "Provider not approved — skip provider tests");
    const r = await api.get("/api/submissions/received", {
      headers: { Authorization: `Bearer ${prov.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });

  test("Provider can view audit list", async ({ api, prov }) => {
    test.skip(!prov.token, "Provider not approved");
    const r = await api.get("/api/audits/", {
      headers: { Authorization: `Bearer ${prov.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });

  test("Provider can view audit templates", async ({ api, prov }) => {
    test.skip(!prov.token, "Provider not approved");
    const r = await api.get("/api/audits/templates", {
      headers: { Authorization: `Bearer ${prov.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });

  test("Provider can view pending NCR", async ({ api, prov }) => {
    test.skip(!prov.token, "Provider not approved");
    const r = await api.get("/api/audits/ncr/pending", {
      headers: { Authorization: `Bearer ${prov.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });

  test("Provider can view certificate registry", async ({ api, prov }) => {
    test.skip(!prov.token, "Provider not approved");
    const r = await api.get("/api/submissions/certificates/registry", {
      headers: { Authorization: `Bearer ${prov.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });

  test("Provider can view auditor list", async ({ api, prov }) => {
    test.skip(!prov.token, "Provider not approved");
    const r = await api.get("/auth/provider/auditors", {
      headers: { Authorization: `Bearer ${prov.token}` },
    });
    expect([200, 307]).toContain(r.status());
  });
});
