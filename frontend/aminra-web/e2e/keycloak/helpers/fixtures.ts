/**
 * Playwright fixtures for Tier 1 Keycloak E2E.
 *
 * Provisions test users in Keycloak per worker, returns direct-grant
 * tokens for fast tests. Browser-flow tests also exist for the few
 * cases that exercise PKCE redirect dance.
 */

import { test as base } from "@playwright/test";
import {
  createUser,
  deleteUser,
  disableUser,
  findUserByEmail,
  getAdminToken,
  loginDirect,
} from "./admin-api";

export interface KcTestUser {
  id: string;
  email: string;
  password: string;
  role: string;
  tenantId: string | null;
  isOwner: boolean;
  status: string;
  accessToken: string;
  refreshToken: string;
}

interface Fixtures {
  adminToken: string;
  /** Business owner user, fast direct-grant token */
  bizUser: KcTestUser;
  /** Auditor user (privileged role — would need MFA in prod) */
  auditorUser: KcTestUser;
  /** CB Admin user */
  cbAdminUser: KcTestUser;
  /** Platform admin user */
  platformAdminUser: KcTestUser;
  /** Second business user in DIFFERENT tenant — cross-tenant tests */
  bizUserB: KcTestUser;
  /** Suspended user (enabled=false) */
  suspendedUser: KcTestUser;
}

const TS = Date.now();
const PW = "TestUserPwd!2026";

async function provision(
  adminToken: string,
  spec: {
    suffix: string;
    role: string;
    tenantId: string | null;
    isOwner?: boolean;
    status?: string;
    enabled?: boolean;
  },
): Promise<KcTestUser> {
  const email = `pw-tier1-${spec.suffix}-${TS}@e2e.vn`;
  const username = email;
  // Cleanup any leftover from previous runs (tolerates 404)
  const existing = await findUserByEmail(adminToken, email);
  if (existing) await deleteUser(adminToken, existing);

  const id = await createUser(adminToken, {
    id: "",
    username,
    email,
    password: PW,
    role: spec.role,
    tenantId: spec.tenantId,
    isOwner: spec.isOwner !== false,
    status: spec.status ?? "active",
    emailVerified: true,
  });

  // For suspended user, disable after creation (skip login)
  if (spec.enabled === false) {
    await disableUser(adminToken, id);
    return {
      id,
      email,
      password: PW,
      role: spec.role,
      tenantId: spec.tenantId,
      isOwner: spec.isOwner !== false,
      status: spec.status ?? "active",
      accessToken: "",
      refreshToken: "",
    };
  }

  const tokens = await loginDirect(email, PW);
  return {
    id,
    email,
    password: PW,
    role: spec.role,
    tenantId: spec.tenantId,
    isOwner: spec.isOwner !== false,
    status: spec.status ?? "active",
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  };
}

export const test = base.extend<Fixtures>({
  adminToken: async ({}, use) => {
    const tok = await getAdminToken();
    await use(tok);
  },

  bizUser: async ({ adminToken }, use) => {
    const u = await provision(adminToken, {
      suffix: "biz",
      role: "business",
      tenantId: "tier1-tenant-A",
    });
    await use(u);
    await deleteUser(adminToken, u.id).catch(() => {});
  },

  bizUserB: async ({ adminToken }, use) => {
    const u = await provision(adminToken, {
      suffix: "biz-b",
      role: "business",
      tenantId: "tier1-tenant-B",
    });
    await use(u);
    await deleteUser(adminToken, u.id).catch(() => {});
  },

  auditorUser: async ({ adminToken }, use) => {
    const u = await provision(adminToken, {
      suffix: "auditor",
      role: "auditor",
      tenantId: null,
      isOwner: false,
    });
    await use(u);
    await deleteUser(adminToken, u.id).catch(() => {});
  },

  cbAdminUser: async ({ adminToken }, use) => {
    const u = await provision(adminToken, {
      suffix: "cbadmin",
      role: "cb_admin",
      tenantId: null,
      isOwner: true,
    });
    await use(u);
    await deleteUser(adminToken, u.id).catch(() => {});
  },

  platformAdminUser: async ({ adminToken }, use) => {
    const u = await provision(adminToken, {
      suffix: "platadmin",
      role: "platform_admin",
      tenantId: null,
      isOwner: true,
    });
    await use(u);
    await deleteUser(adminToken, u.id).catch(() => {});
  },

  suspendedUser: async ({ adminToken }, use) => {
    const u = await provision(adminToken, {
      suffix: "suspended",
      role: "business",
      tenantId: "tier1-tenant-A",
      enabled: false,
    });
    await use(u);
    await deleteUser(adminToken, u.id).catch(() => {});
  },
});

export { expect } from "@playwright/test";
