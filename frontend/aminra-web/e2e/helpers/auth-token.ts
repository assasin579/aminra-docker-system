import { APIRequestContext } from "@playwright/test";

const DEFAULT_KEYCLOAK_URL = "https://auth.aminra.org";
const DEFAULT_REALM = "aminra";
const DEFAULT_CLIENT_ID = "aminra-frontend";

export type KeycloakLogin = {
  email: string;
  password: string;
};

export function keycloakTokenUrl(): string {
  if (process.env.KEYCLOAK_TOKEN_URL) {
    return process.env.KEYCLOAK_TOKEN_URL;
  }
  const keycloakUrl = (
    process.env.PW_KEYCLOAK_URL ||
    process.env.KEYCLOAK_PUBLIC_URL ||
    process.env.KEYCLOAK_URL ||
    process.env.NEXT_PUBLIC_KEYCLOAK_URL ||
    DEFAULT_KEYCLOAK_URL
  ).replace(/\/$/, "");
  const realm =
    process.env.KEYCLOAK_REALM || process.env.NEXT_PUBLIC_KEYCLOAK_REALM || DEFAULT_REALM;

  return `${keycloakUrl}/realms/${encodeURIComponent(realm)}/protocol/openid-connect/token`;
}

export function keycloakClientId(): string {
  return String(
    process.env.KEYCLOAK_PUBLIC_CLIENT_ID ||
    process.env.KEYCLOAK_CLIENT_ID ||
    process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ||
    DEFAULT_CLIENT_ID,
  );
}

function keycloakForwardedHeaders(tokenUrl: string): Record<string, string> | undefined {
  // Local Docker/host E2E can post to Keycloak on 127.0.0.1/keycloak while the
  // backend validates the public issuer. Forwarded headers make Keycloak mint
  // tokens with the same issuer the backend is configured to trust, without
  // sending QA credentials through the public Cloudflare route.
  if (!/(^http:\/\/127\.0\.0\.1|^http:\/\/localhost|^http:\/\/keycloak[:/])/.test(tokenUrl)) {
    return undefined;
  }
  return {
    "X-Forwarded-Proto": process.env.KEYCLOAK_PUBLIC_PROTO || "https",
    "X-Forwarded-Host": process.env.KEYCLOAK_PUBLIC_HOST || "auth.aminra.org",
    "X-Forwarded-Port": process.env.KEYCLOAK_PUBLIC_PORT || "443",
  };
}

/**
 * Modern normal-user token grant for API E2E specs.
 *
 * Phase 4c removed backend `POST /auth/login`; browser E2E must obtain JWTs
 * from Keycloak (or the Next `/api/auth/login` shim when app-profile shape is
 * under test), then keep backend assertions unchanged.
 */
export async function keycloakPasswordGrant(
  request: APIRequestContext,
  { email, password }: KeycloakLogin,
) {
  const tokenUrl = keycloakTokenUrl();
  return request.post(tokenUrl, {
    headers: keycloakForwardedHeaders(tokenUrl),
    form: {
      grant_type: "password" as const,
      client_id: keycloakClientId(),
      username: email,
      password,
    },
  });
}

export async function requireKeycloakUserToken(
  request: APIRequestContext,
  credentials: KeycloakLogin,
): Promise<string> {
  const login = await keycloakPasswordGrant(request, credentials);
  if (!login.ok()) {
    throw new Error(
      `Keycloak token grant failed for ${credentials.email} (${login.status()}); backend /auth/login is retired`,
    );
  }

  const body = await login.json().catch(() => ({}));
  const token = body.access_token;
  if (typeof token !== "string" || token.length === 0) {
    throw new Error(`Keycloak token grant for ${credentials.email} did not return access_token`);
  }
  return token;
}
