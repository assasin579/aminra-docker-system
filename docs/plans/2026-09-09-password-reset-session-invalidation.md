# Password Reset Session Invalidation Implementation Plan

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task if execution is approved.

Goal: When an AMINRA admin changes a user's password, immediately invalidate Keycloak sessions and remove stale browser auth/cache state so old tokens/cached OIDC state cannot keep redirecting or resurrecting the previous login.

Architecture: Treat Keycloak as the source of truth for credentials and sessions. Backend password reset must perform reset-password plus Keycloak session revocation/logout for the target user. Frontend must clear local/session/OIDC storage and auth-critical caches after a successful password change when the edited target is the current user, then force a clean Keycloak login round-trip.

Tech Stack: FastAPI/Python backend, Keycloak Admin REST, Next.js/React frontend, oidc-client-ts, Vitest/Pytest/Playwright.

---

## Acceptance Criteria

1. Admin password reset endpoint resets password and invalidates all active Keycloak sessions for the target user.
2. If the admin changes their own password, the frontend clears AMINRA token/profile keys, OIDC state/user keys, service-worker AMINRA caches, and redirects through Keycloak logout/login so the next page uses a fresh token.
3. If an admin changes another user's password, the target user's existing sessions become invalid; admin's current UI session remains active.
4. No plaintext password is logged, returned, or stored in docs/tests.
5. Failure is fail-closed: if password reset succeeds but session invalidation fails, endpoint returns a non-success error and frontend does not show final success.
6. Regression tests cover backend Keycloak calls and frontend self-reset cleanup behavior.

---

## Task 1: Add Keycloak target-user session invalidation helper

Objective: Extend backend Keycloak admin wrapper to revoke target user sessions after reset.

Files:
- Modify: `backend/auth/keycloak_admin.py`
- Test: `backend/tests/test_admin_user_password_reset.py`

Steps:
1. Add failing tests that assert `reset_user_password(..., invalidate_sessions=True)` calls:
   - `PUT /users/{id}/reset-password`
   - then `POST /users/{id}/logout` or equivalent Keycloak Admin REST endpoint.
2. Add a failure test: if logout endpoint returns non-2xx, raise `KeycloakAdminError` without leaking the password.
3. Implement a helper:
   - `logout_user_sessions(user_id: str) -> None`
   - `reset_user_password(user_id, new_password, temporary=False, invalidate_sessions=True)` calls it after successful password reset.
4. Keep default `invalidate_sessions=True` for admin reset path. Existing create-user flow should not need logout after initial password set.
5. Run: `docker compose exec -T aminra-backend sh -lc 'PYTHONPATH=/app pytest -q tests/test_admin_user_password_reset.py'`

Notes:
- Prefer Keycloak Admin REST `POST /admin/realms/aminra/users/{user-id}/logout` to invalidate all user sessions.
- Do not use realm-wide notBefore unless explicitly needed; it invalidates too broadly.

---

## Task 2: Make admin reset endpoint report whether reset target is current user

Objective: Let frontend distinguish self-password-change from changing another user's password.

Files:
- Modify: `backend/app.py`
- Test: `backend/tests/test_admin_user_password_reset.py`

Steps:
1. Add a backend test that the route contains or returns a field like:
   - `{ "message": "Đã đổi mật khẩu user", "sessions_revoked": true, "self_reset": true|false }`
2. Determine current admin identity from the request token/session.
3. Compare current identity with target user via canonical matching:
   - Keycloak `sub` vs `row.keycloak_sub`, or
   - current email vs `row.email` as fallback.
4. Return `self_reset` boolean.
5. Run focused backend tests.

Security rule:
- The response must never include the new password or token values.

---

## Task 3: Add frontend auth-state purge utility

Objective: Centralize cleanup of AMINRA auth, OIDC state, and auth-critical caches.

Files:
- Create or modify: `frontend/aminra-web/lib/auth-session-cleanup.ts`
- Modify: `frontend/aminra-web/lib/auth-oidc.ts` if OIDC user removal needs wrapping
- Test: `frontend/aminra-web/__tests__/auth-session-cleanup.test.ts`

Steps:
1. Add tests for a `purgeAuthSessionState()` function:
   - removes `aminra_user_token`
   - removes `aminra_user_profile`
   - removes `aminra_admin_token`
   - removes `oidc.*` keys from localStorage/sessionStorage
   - preserves non-auth preferences like `aminra_lang`
   - calls `caches.delete(key)` for keys starting `aminra-`
   - unregisters or updates service worker only if necessary; do not break PWA globally.
2. Implement `purgeAuthSessionState()` as a best-effort async function.
3. Use strict key filtering; do not call `localStorage.clear()` because it can wipe language/preferences/unrelated app data.
4. Run: `cd frontend/aminra-web && npm test -- auth-session-cleanup.test.ts --run`

---

## Task 4: Wire self-reset cleanup into AdminUserManager

Objective: After successful self-password-reset, force clean logout/login so the browser cannot keep stale token/session.

Files:
- Modify: `frontend/aminra-web/components/AdminUserManager.tsx`
- Test: `frontend/aminra-web/__tests__/admin-user-password-reset-session.test.tsx` or extend existing test.

Steps:
1. Add test: when reset endpoint responds `self_reset: true`, frontend calls `purgeAuthSessionState()` and redirects to Keycloak logout/login or shows a controlled re-login prompt.
2. Add test: when `self_reset: false`, frontend does not purge admin's current session.
3. Implement behavior after `pwRes.ok`:
   - parse JSON response
   - if `self_reset`, call `await purgeAuthSessionState()`
   - then call `signoutRedirect()` or navigate to a dedicated `/auth/session-reset` page that starts fresh login.
4. Prefer explicit UX message: “Mật khẩu đã đổi. Vui lòng đăng nhập lại bằng mật khẩu mới.”
5. Run focused frontend tests.

Implementation preference:
- For admin self-reset, end current Keycloak browser SSO session. Otherwise Keycloak may silently reuse old realm cookie and bounce the user back to auth.

---

## Task 5: Add browser smoke for admin self-password-reset

Objective: Prove the bug is fixed in a real browser, not only unit tests.

Files:
- Add/modify: `docs/qa/2026-09-09-admin-password-session-reset/` smoke script or Playwright spec.

Steps:
1. Create a temporary platform-admin QA user.
2. Login via `dev-web.silvergem.org/admin`.
3. Reset that same QA user's password from Admin UI.
4. Assert current browser localStorage/sessionStorage no longer has AMINRA/OIDC auth keys.
5. Assert old token no longer passes `/api/auth/me` or relevant admin route.
6. Login again with the new password and assert Admin Panel renders.
7. Cleanup QA user from Postgres + Keycloak.

---

## Verification Commands

Backend:
```bash
cd /home/user/Documents/aminra-docker-system
docker compose exec -T aminra-backend sh -lc 'PYTHONPATH=/app pytest -q tests/test_admin_user_password_reset.py tests/test_keycloak_admin_unit.py'
```

Frontend:
```bash
cd /home/user/Documents/aminra-docker-system/frontend/aminra-web
npm test -- auth-session-cleanup.test.ts admin-user-password-reset-session.test.tsx --run
npm run lint
npm run build
```

Live smoke:
```bash
cd /home/user/Documents/aminra-docker-system
curl -fsS http://127.0.0.1:8100/health
curl -fsS -o /tmp/admin.html -w 'admin_http=%{http_code}\n' http://127.0.0.1:3100/admin
# Then run the dedicated Playwright/browser self-reset smoke after implementation.
```

---

## Rollback Plan

1. Revert frontend cleanup wiring if it breaks admin UX.
2. Keep backend Keycloak `logout_user_sessions` helper available but guard it behind `invalidate_sessions=True`.
3. If Keycloak logout endpoint behavior differs by version, switch to deleting user sessions discovered via `GET /users/{id}/sessions` if available.

---

## Non-goals

- Do not migrate all tokens to httpOnly cookies in this patch; that is larger Phase 2d hardening.
- Do not clear all browser storage globally.
- Do not invalidate realm-wide sessions for all users on every password reset.
- Do not add MFA or password policy changes in this patch.
