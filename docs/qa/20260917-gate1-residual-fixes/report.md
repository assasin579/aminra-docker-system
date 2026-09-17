# AMINRA Gate 1 — Residual Fix Follow-up

Date: 2026-09-17
Scope: safe residual fixes after Gate 1 PASS candidate; no commit/deploy performed.

## Verdict

PASS for targeted residual verification.

This follow-up does **not** replace the final Gate 1 runner evidence at `docs/qa/20260917-gate1-onboarding-final/`; it closes two residual backlog items:

1. Public `/health` frontend contract mismatch.
2. Active auth-domain defaults still pointing at legacy `auth.silvergem.org` in executable paths.

## Changes

- Added frontend public `GET /health` route that proxies backend `/health` with `Cache-Control: no-store`.
- Added Playwright contract coverage for public frontend `/health`.
- Updated active Keycloak fallback defaults from `https://auth.silvergem.org` to `https://auth.aminra.org` in:
  - `frontend/aminra-web/app/api/auth/login/route.ts`
  - `scripts/pre_demo_check.sh`
- Added backend contract assertion that active auth defaults stay canonical and do not regress to `auth.silvergem.org`.

## Verification

- Backend contract tests in container: `7 passed`
  - Command: `docker compose exec -T aminra-backend pytest -q tests/test_gate1_runner_contract.py tests/test_repair_demo_accounts_contract.py`
- Frontend lint: PASS
  - Command: `npm run lint`
- Frontend production build: PASS
  - Command: `npm run build`
  - `/health` appears as a dynamic route in the Next route manifest.
  - Sentry deprecation warnings remain pre-existing and non-blocking for this patch.
- Local Next start smoke on port `3217`: PASS
  - `GET http://127.0.0.1:3217/health` returned HTTP `200`
  - Body: `status=ok`, `database=connected`, `qdrant=connected`
  - Header: `cache-control: no-store`
- Focused Playwright health spec against the built app on port `3217`: `4 passed`
  - Command: `PW_BASE_URL=http://127.0.0.1:3217 PW_API_BASE=http://127.0.0.1:8100 npx playwright test e2e/01-health.spec.ts --project=desktop-chromium`
- Diff hygiene: PASS
  - Command: `git diff --check`
- Active executable-domain audit: PASS
  - No `auth.silvergem.org` matches in `frontend/aminra-web/app`, `scripts/pre_demo_check.sh`, or `scripts/qa/run-gate1-onboarding.sh`.

## Remaining residuals

- 26 skipped desktop Chromium tests from Gate 1 final evidence still require review/classification before customer handoff.
- Accessibility/color-contrast warnings still require focused mobile/a11y follow-up.
- No commit/deploy was performed; running production container on `:3100` will not expose the new `/health` route until the frontend image is rebuilt/recreated under founder authorization.
