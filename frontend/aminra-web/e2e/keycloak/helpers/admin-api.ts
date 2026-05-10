/**
 * Keycloak admin REST helper for Tier 1 Playwright E2E.
 *
 * Uses the master-realm admin credentials (test env). NOT for production
 * — production uses the aminra-admin-cli service account. Tests need
 * admin powers to inspect events / wipe sessions / manage all users.
 */

import { request, type APIRequestContext } from "@playwright/test";

const KC_URL = process.env.KEYCLOAK_URL ?? "http://localhost:8180";
const KC_REALM = "aminra";
const ADMIN_USER = "admin";
const ADMIN_PASSWORD =
  process.env.KEYCLOAK_ADMIN_PASSWORD ?? "admin_test_pw_2026_change_me";

export interface KcUser {
  id: string;
  username: string;
  email: string;
  password: string;
  role: string;
  tenantId?: string | null;
  isOwner?: boolean;
  status?: string;
  emailVerified?: boolean;
  totpEnabled?: boolean;
}

/** Acquires the admin token from master realm. */
export async function getAdminToken(api?: APIRequestContext): Promise<string> {
  const ctx = api ?? (await request.newContext());
  const res = await ctx.post(`${KC_URL}/realms/master/protocol/openid-connect/token`, {
    form: {
      username: ADMIN_USER,
      password: ADMIN_PASSWORD,
      grant_type: "password",
      client_id: "admin-cli",
    },
  });
  if (!res.ok()) {
    throw new Error(`Admin token fetch failed: ${res.status()} ${await res.text()}`);
  }
  const body = await res.json();
  return body.access_token;
}

/** Get realm role detail by name. */
export async function getRole(token: string, role: string): Promise<{ id: string; name: string }> {
  const ctx = await request.newContext();
  const res = await ctx.get(`${KC_URL}/admin/realms/${KC_REALM}/roles/${role}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok()) throw new Error(`Get role ${role} failed: ${res.status()}`);
  return res.json();
}

/** Create user with attributes + role + email-verified state. */
export async function createUser(
  token: string,
  user: KcUser,
): Promise<string> {
  const ctx = await request.newContext();
  const attributes: Record<string, string[]> = {
    is_owner: [user.isOwner === false ? "false" : "true"],
    status: [user.status ?? "active"],
  };
  if (user.tenantId !== undefined && user.tenantId !== null) {
    attributes.tenant_id = [user.tenantId];
  }

  const create = await ctx.post(`${KC_URL}/admin/realms/${KC_REALM}/users`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    data: {
      username: user.username,
      email: user.email,
      firstName: user.username.split("@")[0],
      lastName: "TestUser",
      enabled: true,
      emailVerified: user.emailVerified ?? true,
      attributes,
      requiredActions: [],
      credentials: [{ type: "password", value: user.password, temporary: false }],
    },
  });
  if (!create.ok()) {
    throw new Error(`Create user failed: ${create.status()} ${await create.text()}`);
  }
  const location = create.headers().location ?? "";
  const userId = location.split("/").filter(Boolean).pop() ?? "";
  if (!userId) {
    throw new Error(`Create user: no Location header (got "${location}")`);
  }

  // Re-clear required actions (Keycloak may auto-add VERIFY_EMAIL despite payload)
  await ctx.put(`${KC_URL}/admin/realms/${KC_REALM}/users/${userId}`, {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    data: { requiredActions: [] },
  });

  // Grant role
  const role = await getRole(token, user.role);
  const grant = await ctx.post(
    `${KC_URL}/admin/realms/${KC_REALM}/users/${userId}/role-mappings/realm`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      data: [{ id: role.id, name: role.name }],
    },
  );
  if (!grant.ok()) {
    throw new Error(`Grant role failed: ${grant.status()}`);
  }

  return userId;
}

/** Delete user by id (cleanup). */
export async function deleteUser(token: string, userId: string): Promise<void> {
  const ctx = await request.newContext();
  await ctx.delete(`${KC_URL}/admin/realms/${KC_REALM}/users/${userId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

/** Find user by email; returns id or null. */
export async function findUserByEmail(token: string, email: string): Promise<string | null> {
  const ctx = await request.newContext();
  const res = await ctx.get(
    `${KC_URL}/admin/realms/${KC_REALM}/users?email=${encodeURIComponent(email)}&exact=true`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!res.ok()) return null;
  const list = await res.json();
  return Array.isArray(list) && list.length > 0 ? list[0].id : null;
}

/** Direct password grant for fast test auth (skip browser). */
export async function loginDirect(
  email: string,
  password: string,
): Promise<{ access_token: string; refresh_token: string }> {
  const ctx = await request.newContext();
  const res = await ctx.post(
    `${KC_URL}/realms/${KC_REALM}/protocol/openid-connect/token`,
    {
      form: {
        username: email,
        password,
        grant_type: "password",
        client_id: "aminra-frontend",
        scope: "openid profile email",
      },
    },
  );
  if (!res.ok()) {
    throw new Error(
      `Direct login failed for ${email}: ${res.status()} ${await res.text()}`,
    );
  }
  return res.json();
}

/** Add required actions to user (e.g., force CONFIGURE_TOTP). */
export async function setRequiredActions(
  token: string,
  userId: string,
  actions: string[],
): Promise<void> {
  const ctx = await request.newContext();
  const res = await ctx.put(`${KC_URL}/admin/realms/${KC_REALM}/users/${userId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    data: { requiredActions: actions },
  });
  if (!res.ok()) {
    throw new Error(`Set required actions failed: ${res.status()}`);
  }
}

/** Disable user (simulate suspended). */
export async function disableUser(token: string, userId: string): Promise<void> {
  const ctx = await request.newContext();
  await ctx.put(`${KC_URL}/admin/realms/${KC_REALM}/users/${userId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    data: { enabled: false },
  });
}

/** Logout all sessions of a user. */
export async function logoutAllSessions(token: string, userId: string): Promise<void> {
  const ctx = await request.newContext();
  await ctx.post(`${KC_URL}/admin/realms/${KC_REALM}/users/${userId}/logout`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export { KC_URL, KC_REALM };
