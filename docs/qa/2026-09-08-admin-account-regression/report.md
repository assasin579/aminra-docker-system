# AMINRA QA Report — Admin account regression sweep (2026-09-08)

## Verdict

**PASS for controlled sandbox admin usage on `https://dev-web.silvergem.org/admin`.**

The admin password-reset false-success class did **not** recur in the backend/API flow, and the authenticated browser admin panel rendered without blocking API or console errors after a real Keycloak SSO login with a temporary `platform_admin` account.

**Still not a customer/unsupervised pilot approval.** Existing project-level blockers remain: Keycloak SMTP/verifyEmail and broader auth/session hardening.

## Scope

Validated with temporary QA-only accounts and temporary QA-only data:

- Admin SSO login authority: Keycloak realm role `platform_admin`.
- Admin read endpoints: verify, doc types, templates, placeholders, users.
- Admin template reference-file upload/delete using QA-only text file, not official template overwrite.
- Placeholder CRUD using QA-only key.
- User CRUD using QA-only target account.
- Dedicated admin password reset endpoint and real Keycloak login outcome after reset.
- Negative authorization: non-admin target token cannot access admin user API.
- Browser smoke: `/admin` login through Keycloak SSO, admin shell/sidebar/tabs visible, no blocking API/console failures.

## Evidence

- Raw API smoke result: `docs/qa/2026-09-08-admin-account-regression/evidence/raw/admin-api-smoke.json`
- Raw browser smoke result: `docs/qa/2026-09-08-admin-account-regression/evidence/raw/admin-browser-smoke.json`
- Browser screenshot: `docs/qa/2026-09-08-admin-account-regression/evidence/screenshots/admin-browser-panel.png`

## Automated gates run

```text
Backend focused admin/auth regression:
docker compose exec -T aminra-backend pytest \
  tests/test_admin_user_password_reset.py \
  tests/test_demo_account_login_smoke_script.py \
  tests/test_keycloak_admin_unit.py \
  tests/test_keycloak_admin_edge.py -q
=> 86 passed in 0.55s

Frontend lint:
cd frontend/aminra-web && npm run lint
=> pass

Frontend production build:
cd frontend/aminra-web && npm run build
=> pass

Whitespace gate:
git diff --check
=> pass
```

## Live API smoke results

`24 / 24` live checks passed:

- `admin_token_platform_admin` → `200`
- `admin_verify` → `200`
- `admin_doc_types` → `200`
- `admin_templates_list` → `200`
- `admin_placeholders_list` → `200`
- `admin_users_list` → `200`
- `admin_template_get` → `200`
- `admin_template_files_list` → `200`
- `admin_template_files_list_vi` → `200`
- `admin_template_lang_files_list` → `200`
- `admin_template_revisions` → `200`
- `admin_reference_file_upload_delete_upload` → `200`
- `admin_reference_file_upload_delete_delete` → `200`
- `admin_placeholder_create` → `200`
- `admin_placeholder_update` → `200`
- `admin_placeholder_delete` → `200`
- `admin_user_create` → `200`
- `admin_user_search_read` → `200` with `total=1`
- `admin_user_profile_update` → `200`
- `admin_user_password_reset_endpoint` → `200`
- `admin_user_password_reset_old_rejected` → old password rejected with `401` after reset
- `admin_user_password_reset_new_accepted` → new password accepted with `200`
- `non_admin_blocked_from_admin_users` → non-admin blocked with `403`
- `admin_user_delete` → `200`

## Live browser smoke results

`6 / 6` checks passed on `https://dev-web.silvergem.org/admin`:

- Authenticated admin panel reached.
- Session persisted after Keycloak callback.
- Logged-out screen was not shown.
- User-management/admin markers visible.
- No blocking admin API errors detected.
- No blocking browser console errors detected.

Visible authenticated admin navigation/sections from screenshot:

- Admin Panel
- Analytics
- Audit logs
- Overdue queue
- Standards
- Industries ↔ Standards
- Template đánh giá
- Placeholders
- Quản lý Users

## Cleanup verification

- Temporary API target user was deleted through product admin API.
- Temporary Keycloak admin/browser smoke accounts were deleted in cleanup traps.
- Browser SSO `/auth/me` auto-projected one temporary browser admin into the app DB; it was removed by exact QA email-pattern cleanup.
- Follow-up cleanup query found no leftover `qa-admin-browser*`, `qa-admin-full*`, or `qa-admin-target*` Keycloak users.
- Final DB cleanup query found:
  - `0` users with `email ILIKE 'qa-admin-%@aminra.local'`
  - `0` custom placeholders with `key ILIKE 'qa_admin_smoke_%'`

## Notes / limitations

- The first browser-smoke attempt stopped at the logged-out admin landing screen because the script matched multiple “Đăng nhập Admin” buttons and did not click the Keycloak SSO button. This was a test-script selector issue, not a product failure. The selector was corrected to click the explicit `Keycloak SSO` button, then the browser smoke passed.
- The browser smoke validates admin shell/navigation and initial admin data loads. It does not exhaustively click every admin tab sub-action/modal.
- Admin credential correctness is now tested by actual Keycloak token exchange and post-reset old/new password behavior, not by trusting app DB rows.

## Recommendation

P0 before any real customer pilot remains unchanged: configure Keycloak SMTP/verified-domain email, re-enable `verifyEmail=true`, and add this admin API + browser smoke as a repeatable CI/pre-demo script instead of one-off QA.
