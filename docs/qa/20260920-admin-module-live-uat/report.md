# AMINRA Admin Tenant Modules — Live Browser UAT

## Verdict

**PASS for sandbox operator UAT.** Platform-admin browser session can open the new **Tenant modules** tab, load a real sandbox tenant module inventory, perform a safe idempotent module status save through the deployed Next proxy/backend API, and see backend fail-closed policy detail when attempting to disable a required/default module.

This is **not** a production/customer-pilot GO by itself; broad runtime guard enablement still requires scoped rollout, live-token route UAT, rollback criteria, and unrelated SMTP/edge/dependency gates.

## Environment

- Repo: `/home/user/Documents/aminra-docker-system`
- Branch/commit under test: `dev` / `0f6d103 fix(frontend): proxy PATCH admin module updates`
- Runtime: local sandbox Docker Compose after immutable deploy
- Frontend: `http://localhost:3100/admin`
- Backend health: covered by immutable deploy phase gate
- Auth: platform-admin Keycloak token from gitignored QA credentials; credentials/tokens are not recorded here.
- Tenant under test: `8cdc80c4-5be5-4bc8-b07e-5a18ac611a11`

## Acceptance criteria

1. Platform admin can access Admin Panel without legacy `aminra_admin_token`.
2. **Tenant modules** tab is visible and renders the module console.
3. Admin can load modules for a real sandbox tenant via `/api/auth/admin/tenants/{tenant_id}/modules`.
4. Admin can perform a safe idempotent status save through deployed `PATCH` proxy path.
5. Backend policy blocks disabling required/default module and UI surfaces the policy detail instead of false success.
6. No material browser console/page errors beyond the expected 409 Conflict for the negative-policy check.

## Execution

Command:

```bash
cd frontend/aminra-web
set -a; source ../../.env; source ../../.qa/aminra-demo-credentials.env; set +a
UAT_EVIDENCE_DIR="$PWD/../../docs/qa/20260920-admin-module-live-uat/evidence" \
UAT_TENANT_ID="8cdc80c4-5be5-4bc8-b07e-5a18ac611a11" \
npx playwright test e2e/tmp-admin-module-live-uat.spec.ts --project=desktop-chromium --reporter=line
```

Result:

```text
1 passed (8.2s)
```

## Evidence

- `evidence/01-admin-module-tab.png` — Admin panel with **Tenant modules** tab opened.
- `evidence/02-modules-loaded.png` — Real tenant module inventory loaded with business model and status controls.
- `evidence/03-safe-idempotent-save.png` — Safe idempotent `supplier_management → enabled` save succeeded through deployed `PATCH` route.
- `evidence/04-required-module-blocked.png` — Attempt to disable required/default `supplier_management` blocked with `MODULE_REQUIRED:supplier_management` surfaced in UI.

## Important finding fixed during UAT

Initial live UAT found the Admin UI component was correct but the Next catch-all proxy lacked an exported `PATCH` handler, so the browser received `405` and the UI could only show fallback failure text. Fixed with:

- `frontend/aminra-web/app/api/[...path]/route.ts` — added `export async function PATCH(...)`.
- `frontend/aminra-web/__tests__/public-trace-proxy-cache-contract.test.ts` — added regression proving PATCH is proxied to backend instead of Next returning 405.

Verification after fix:

```text
public-trace-proxy-cache-contract.test.ts + admin-module-manager-contract.test.tsx: 6 passed
npm run lint: PASS
npm run build: PASS
immutable deploy: PASS, evidence docs/qa/20260920-202520-modularization-phase-gate
live browser UAT: 1 passed
```

## Caveats / next

- Temporary Playwright UAT spec was used for execution and removed after capture; durable coverage is kept by the committed proxy/component contract tests.
- Do not broadly enable `MODULE_GUARDS_ENABLED=true` yet. Next runtime enablement should use scoped `MODULE_GUARD_ROLLOUT=supplier_management,process_digitization,traceability,public_trace` plus rollback and live route UAT.
