import { test as base, APIRequestContext, request } from "@playwright/test";

const API_BASE = process.env.PW_API_BASE ?? "http://localhost:8100";

export type Persona = {
  api:      APIRequestContext;
  apiBase:  string;
  biz:      { email: string; password: string; token: string };
  prov:     { email: string; password: string; token: string };
  admin:    { token: string };
};

export const test = base.extend<Persona>({
  apiBase: async ({}, use) => { await use(API_BASE); },

  api: async ({ apiBase }, use) => {
    const ctx = await request.newContext({ baseURL: apiBase });
    await use(ctx);
    await ctx.dispose();
  },

  /* Shared business account — registered once per worker */
  biz: async ({ api }, use) => {
    const ts = Date.now();
    const email = `pw-biz-${ts}@e2e.vn`;
    const password = `Pw${ts}Pass!`;

    await api.post("/auth/business/register", {
      data: { email, password, company_name: `PW Biz ${ts}` },
    });
    const res = await api.post("/auth/login", { data: { email, password } });
    const body = await res.json().catch(() => ({}));
    await use({ email, password, token: body.access_token ?? "" });
  },

  /* Shared provider account — admin-approved */
  prov: async ({ api, admin }, use) => {
    const ts = Date.now() + 1;
    const email = `pw-prov-${ts}@e2e.vn`;
    const password = `Pw${ts}Pass!`;

    await api.post("/auth/provider/register", {
      data: { email, password, company_name: `PW Provider ${ts}` },
    });

    /* Find + approve via admin */
    if (admin.token) {
      const pend = await api.get("/auth/admin/pending-providers", {
        headers: { Authorization: `Bearer ${admin.token}` },
      });
      const list = await pend.json().catch(() => []);
      const found = Array.isArray(list)
        ? list.find((p: { email: string }) => p.email === email)
        : null;
      if (found) {
        const pid = found.id ?? found.user_id;
        await api.post(`/auth/admin/providers/${pid}/approve`, {
          headers: { Authorization: `Bearer ${admin.token}` },
        });
      }
    }

    const res = await api.post("/auth/login", { data: { email, password } });
    const body = await res.json().catch(() => ({}));
    await use({ email, password, token: body.access_token ?? "" });
  },

  /* Admin */
  admin: async ({ api }, use) => {
    const res = await api.post("/admin/login", {
      data: { username: "admin", password: "aminra2026" },
    });
    const body = await res.json().catch(() => ({}));
    await use({ token: body.token ?? body.access_token ?? "" });
  },
});

export { expect } from "@playwright/test";
