/**
 * Keycloak OIDC PKCE client (ADR-005 Phase 2a).
 *
 * UserManager singleton wrapping `oidc-client-ts`. Initialised lazily so
 * the module is safe to import at SSR build time even when env vars
 * aren't present.
 *
 * Phase 2a scope: provide signinRedirect / handleCallback / getUser /
 * signoutRedirect. Phase 2c will roll forward to all 4 auth pages and
 * Phase 2d will move tokens out of localStorage into httpOnly cookies.
 *
 * Feature flag: NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED. When false, callers
 * must NOT invoke this module — the legacy email/password path stays
 * authoritative. `isOidcEnabled()` is the canonical check.
 */

import {
  Log,
  User,
  UserManager,
  WebStorageStateStore,
  type UserManagerSettings,
} from "oidc-client-ts";

let _manager: UserManager | null = null;

export function isOidcEnabled(): boolean {
  return process.env.NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED === "true";
}

function buildSettings(): UserManagerSettings {
  const authority = process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? "http://localhost:8180";
  const realm = process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "aminra";
  const clientId = process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "aminra-frontend";
  // Public origin where the callback page lives. Falls back to current origin
  // at runtime — required for SSR-friendly init.
  const origin =
    typeof window !== "undefined"
      ? window.location.origin
      : process.env.NEXT_PUBLIC_APP_ORIGIN ?? "http://localhost:3100";

  return {
    authority: `${authority}/realms/${realm}`,
    client_id: clientId,
    redirect_uri: `${origin}/auth/callback`,
    post_logout_redirect_uri: `${origin}/`,
    response_type: "code",
    scope: "openid profile email",
    automaticSilentRenew: true,
    // PKCE is enabled by default in v3+ for public clients
    loadUserInfo: false,
    // Persist state during the redirect round-trip in sessionStorage so a
    // browser refresh during the auth dance doesn't lose it. Tokens
    // themselves stay in memory (UserManager) — Phase 2d hardening will
    // move refresh-token to a httpOnly cookie via Next.js Route Handler.
    stateStore:
      typeof window !== "undefined"
        ? new WebStorageStateStore({ store: window.sessionStorage })
        : undefined,
  };
}

export function getOidcManager(): UserManager {
  if (_manager) return _manager;
  if (typeof window === "undefined") {
    throw new Error("OIDC manager requires a browser context");
  }
  if (!isOidcEnabled()) {
    throw new Error(
      "OIDC requested but NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED=false",
    );
  }
  _manager = new UserManager(buildSettings());
  if (process.env.NODE_ENV !== "production") {
    Log.setLogger(console);
    Log.setLevel(Log.WARN);
  }
  return _manager;
}

export async function signinRedirect(returnTo?: string): Promise<void> {
  const mgr = getOidcManager();
  // `prompt=login` forces Keycloak to show the credentials form even if
  // the realm session cookie is already set. Without it, a user who
  // logs out on the FE but whose Keycloak realm cookie is still valid
  // would be silently re-authenticated as the same identity on the
  // next signin click. This also lets users on a shared device pick a
  // different account.
  await mgr.signinRedirect({
    state: returnTo ?? "/",
    extraQueryParams: { prompt: "login" },
  });
}

export async function handleSigninCallback(): Promise<{
  user: User;
  returnTo: string;
}> {
  const mgr = getOidcManager();
  const user = await mgr.signinRedirectCallback();
  // `state` is whatever signinRedirect set; default to "/"
  const stateValue =
    typeof user.state === "string" ? user.state : "/";
  return { user, returnTo: stateValue };
}

export async function getOidcUser(): Promise<User | null> {
  if (!isOidcEnabled()) return null;
  if (typeof window === "undefined") return null;
  const mgr = getOidcManager();
  return mgr.getUser();
}

export async function signoutRedirect(): Promise<void> {
  if (!isOidcEnabled()) return;
  const mgr = getOidcManager();
  try {
    await mgr.signoutRedirect();
    return;
  } catch {
    // UserManager.signoutRedirect requires an active stored user. If
    // local state was already cleared (e.g. by a parallel tab), the
    // call throws — fall back to a direct end-session URL so the
    // realm cookie is cleared anyway.
    try {
      await mgr.removeUser();
    } catch {}
    if (typeof window !== "undefined") {
      const authority =
        process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? "http://localhost:8180";
      const realm = process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "aminra";
      const clientId =
        process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "aminra-frontend";
      const postLogout = encodeURIComponent(`${window.location.origin}/`);
      window.location.href =
        `${authority}/realms/${realm}/protocol/openid-connect/logout` +
        `?post_logout_redirect_uri=${postLogout}&client_id=${clientId}`;
    }
  }
}

/** Reset module state. Used by tests only. */
export function _resetOidcManagerForTests(): void {
  _manager = null;
}
