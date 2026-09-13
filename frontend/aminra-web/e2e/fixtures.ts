import { test as base, APIRequestContext, request } from "@playwright/test";
import { requireAdminToken } from "./helpers/admin-token";
import { requireKeycloakUserToken } from "./helpers/auth-token";

const API_BASE = process.env.PW_API_BASE ?? "http://localhost:8100";
const BIZ_EMAIL = process.env.PW_BIZ_EMAIL ?? "biz-demo-1@demo.aminra.vn";
const BIZ_PASSWORD = process.env.PW_BIZ_PASSWORD ?? process.env.DEMO_PW;
const PROV_EMAIL = process.env.PW_PROVIDER_EMAIL ?? "cb-demo@demo.aminra.vn";
const PROV_PASSWORD = process.env.PW_PROVIDER_PASSWORD ?? process.env.PROVIDER_DEMO_PW ?? process.env.DEMO_PW;

export type Persona = {
  api: APIRequestContext;
  apiBase: string;
  biz: { email: string; password: string; token: string };
  prov: { email: string; password: string; token: string };
  admin: { token: string };
};

export const test = base.extend<Persona>({
  apiBase: async ({}, use) => {
    await use(API_BASE);
  },

  api: async ({ apiBase }, use) => {
    const ctx = await request.newContext({ baseURL: apiBase });
    await use(ctx);
    await ctx.dispose();
  },

  /* Shared seeded business account. Dynamic backend register→login is obsolete:
     backend /auth/login is retired and Keycloak owns credentials. */
  biz: async ({ api }, use) => {
    const email = BIZ_EMAIL;
    const password = BIZ_PASSWORD;
    if (!password) {
      test.skip(true, "business Keycloak password not configured (PW_BIZ_PASSWORD or DEMO_PW)");
      return;
    }
    const token = await requireKeycloakUserToken(api, { email, password });
    await use({ email, password, token });
  },

  /* Shared seeded provider account. */
  prov: async ({ api }, use) => {
    const email = PROV_EMAIL;
    const password = PROV_PASSWORD;
    if (!password) {
      test.skip(true, "provider Keycloak password not configured (PW_PROVIDER_PASSWORD/PROVIDER_DEMO_PW or DEMO_PW)");
      return;
    }
    const token = await requireKeycloakUserToken(api, { email, password });
    await use({ email, password, token });
  },

  /* Admin */
  admin: async ({ api }, use) => {
    await use({ token: await requireAdminToken(api) });
  },
});

export { expect } from "@playwright/test";
