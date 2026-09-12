import { APIRequestContext, test } from "@playwright/test";

/**
 * Resolve a Keycloak platform_admin token for admin E2E specs.
 *
 * Phase 4c removed the legacy opaque `/admin/login` session. Specs must either
 * receive PW_ADMIN_TOKEN directly or authenticate a real Keycloak admin user via
 * TEST_ADMIN_EMAIL + TEST_ADMIN_PASSWORD. If neither is configured, skip rather
 * than failing against a deliberately removed endpoint.
 */
export async function requireAdminToken(request: APIRequestContext): Promise<string> {
  const direct = process.env.PW_ADMIN_TOKEN;
  if (direct) return direct;

  const email = process.env.TEST_ADMIN_EMAIL;
  const password = process.env.TEST_ADMIN_PASSWORD;
  if (!email || !password) {
    test.skip(true, "admin Keycloak credentials not configured (PW_ADMIN_TOKEN or TEST_ADMIN_EMAIL/TEST_ADMIN_PASSWORD)");
  }

  const keycloakUrl = (process.env.KEYCLOAK_PUBLIC_URL || process.env.NEXT_PUBLIC_KEYCLOAK_URL || "https://auth.silvergem.org").replace(/\/$/, "");
  const realm = process.env.KEYCLOAK_REALM || process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "aminra";
  const clientId = process.env.KEYCLOAK_PUBLIC_CLIENT_ID || process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "aminra-frontend";

  const login = await request.post(`${keycloakUrl}/realms/${realm}/protocol/openid-connect/token`, {
    form: {
      grant_type: "password",
      client_id: clientId,
      username: email,
      password,
    },
  });
  if (!login.ok()) {
    test.skip(true, `admin Keycloak token grant failed (${login.status()}); check TEST_ADMIN_EMAIL/TEST_ADMIN_PASSWORD`);
  }

  const body = await login.json().catch(() => ({}));
  const token = body.access_token;
  if (!token) {
    test.skip(true, "admin Keycloak login did not return access_token");
  }
  return token;
}
