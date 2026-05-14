/**
 * Admin token helper.
 *
 * Phase 4c (2026-05-14): admin auth is unified under Keycloak SSO — the same
 * `aminra_user_token` that holds the regular user JWT also carries the admin
 * identity when its `realm_access.roles` contains `platform_admin`. The
 * legacy opaque-session `aminra_admin_token` was retired with the cutover.
 *
 * Any page calling `/api/admin/*` MUST use `readAdminToken()` so it picks up
 * the token from whichever storage the SSO callback used (localStorage or
 * sessionStorage). The regression gate
 * `e2e/21-admin-pages-token-pattern.spec.ts` enforces this.
 */

const USER_TOKEN_KEY = "aminra_user_token";

export function readAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    localStorage.getItem(USER_TOKEN_KEY) ||
    sessionStorage.getItem(USER_TOKEN_KEY) ||
    null
  );
}
