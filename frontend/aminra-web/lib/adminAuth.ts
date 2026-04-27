/**
 * Admin token helper — DO NOT inline localStorage reads in admin pages.
 *
 * AMINRA has two parallel admin auth flows that are unified at the backend
 * (see backend/auth/jwt_utils.py:require_admin). The frontend must accept
 * either token because the same admin user can arrive via either route:
 *
 *   1. Legacy /admin/login         → opaque session in `aminra_admin_token`
 *   2. /provider/login w/ admin email → JWT in `aminra_user_token`
 *
 * Any page calling `/api/auth/admin/*` MUST use `readAdminToken()` so both
 * flows work. A regression gate in
 * `e2e/21-admin-pages-token-pattern.spec.ts` enforces this.
 */

const USER_TOKEN_KEY  = 'aminra_user_token';
const ADMIN_TOKEN_KEY = 'aminra_admin_token';

export function readAdminToken(): string | null {
  if (typeof window === 'undefined') return null;
  return (
    localStorage.getItem(ADMIN_TOKEN_KEY)  ||
    localStorage.getItem(USER_TOKEN_KEY)   ||
    sessionStorage.getItem(USER_TOKEN_KEY) ||
    null
  );
}
