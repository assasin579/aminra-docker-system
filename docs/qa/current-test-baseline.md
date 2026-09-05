# AMINRA Current Test Baseline — working document

Started: 2026-09-02

## Known baseline from project brain

- Next production build: previously passed on 2026-09-02.
- Runtime health/smoke: canonical demo URLs are `http://localhost:3100` for local and `https://dev-web.silvergem.org` for public sandbox demo.
- `fe.silvergem.org`: non-canonical legacy/hostname path with known 502/tunnel drift; keep out of demo scripts/docs until ownership is fixed. Do not use it as a release/demo gate unless explicitly testing hostname drift.
- Frontend Vitest snapshot from brain: `181 passed / 19 failed`.
- Targeted backend auth/security snapshot from brain: `104 passed / 1 failed`.
- Full backend pytest in runtime container snapshot from brain: `643 passed / 367 skipped / 176 failed / 324 errors`.

## Policy

- Release-blocking suites must be small, deterministic, and green.
- Known-red legacy/full suites must be classified before they can block or unblock readiness.
- A bug fix must add a regression test first, then fix after approval.

## Latest focused verification — 2026-09-02

- `bash -n scripts/qa/runtime-smoke.sh && make runtime-smoke` → **PASS: 12 / WARN: 0 / FAIL: 0**.
  - Local backend/FE reachable.
  - DB + Qdrant connected.
  - `https://dev-web.silvergem.org` reachable.
  - Keycloak OIDC discovery reachable.
  - Fresh logs had no high-signal error patterns in the last 30 minutes.
- `docker compose exec -T aminra-backend sh -c 'cd /app && . /vault/secrets/env.sh && PYTHONPATH=/app pytest tests/test_generate_document_export_security.py tests/test_supply_chain_suppliers.py tests/test_supply_chain_batches.py -q'` → **104 passed**.
- `cd frontend/aminra-web && npm run test -- __tests__/landing-keycloak-cta.test.tsx` → **3 passed**.
- `bash scripts/pre_demo_check.sh` after seeded sandbox data → **PASS: 32 / WARN: 1 / FAIL: 0**.
  - Warning: admin smoke skipped until `ADMIN_DEMO_PW` is provided.
  - Host `.env` currently has `KEYCLOAK_ADMIN_PASSWORD` and `KEYCLOAK_ADMIN_CLI_SECRET`, but not `ADMIN_DEMO_PW` / `TEST_ADMIN_PASSWORD`.
- `make keycloak-email-check` → **PENDING/BLOCKED for production email**:
  - `verifyEmail` currently false in live realm.
  - SMTP host/from/transport security missing in live realm.
  - Per product decision 2026-09-02: keep SMTP live-send pending; do not block sandbox demo.
- `docker compose exec -T aminra-backend sh -c 'cd /app && . /vault/secrets/env.sh && PYTHONPATH=/app pytest tests/test_unauth_route_boundaries.py tests/test_certificate_pdf_integrity_smoke.py tests/test_generate_document_export_security.py tests/test_supply_chain_suppliers.py tests/test_supply_chain_batches.py -q'` → **135 passed**.
  - Adds anonymous-boundary coverage for 26 high-risk protected/public routes.
  - Adds certificate/PDF integrity smoke: public field minimization, unknown cert 404, anonymous PDF/doc generation rejection.
- `cd frontend/aminra-web && npx playwright test e2e/38-demo-spine-keycloak.spec.ts --project=desktop-chromium` → **3 passed** after installing Chromium browser cache with `npx playwright install chromium`.
  - Covers anonymous public verify/trace/forgot-password surfaces.
  - Covers business token protected endpoints via Keycloak password grant.
  - Covers provider token protected endpoints plus business denied provider-only cert issuance.

## Next commands to run in order

1. To finish admin smoke, set `ADMIN_DEMO_PW` for `demo-platform-admin@aminra.vn` or set `ADMIN_DEMO_EMAIL` + `ADMIN_DEMO_PW`, then re-run `bash scripts/pre_demo_check.sh`.
2. Keep SMTP pending until real relay credentials exist; then run `bash scripts/keycloak-bootstrap.sh` + `make keycloak-email-check`.
3. Expand negative tests from representative smoke to full route inventory, prioritizing `public/unknown` and `tenant note: unknown` entries.
4. If frontend surface changes continue, run `cd frontend/aminra-web && npm run build` before commit/release.
5. Keep using focused FE Vitest/Playwright paths; `npm run test -- --runInBand` is Jest syntax and invalid for Vitest.

## Open classification queue

- FE 19 legacy failures from project brain: not re-run in this focused pass; classify as valid regression/stale expectation/env-dependent/flaky before using as release signal.
- BE 1 targeted failure from project brain: not reproduced in this focused pass; current supply-chain/document-export focused suite is green.
- Full BE 176 failures/324 errors: quarantine as legacy/full-suite debt until classified; do not use as a simple release yes/no signal.
