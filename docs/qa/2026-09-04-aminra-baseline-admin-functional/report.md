# AMINRA QA Report — Test Baseline Triage, Admin Smoke, Functional Testing

Date: 2026-09-04
Scope: local controlled sandbox demo readiness; test baseline triage; admin smoke; functional smoke.
Repo: `/home/user/Documents/aminra-docker-system`
Branch: `dev`
Commit at start: `68eb3fef8a507a815845be3ef0ff85a0d6cc5506`
Data safety: read-only smoke except existing deterministic sandbox auth/token checks. No commit/push/deploy performed.

## Executive verdict

- **Controlled sandbox demo:** GO on `localhost:3100` and `https://dev-web.silvergem.org`.
- **Admin smoke Flow 18/20:** PASS when an explicit `ADMIN_DEMO_PW` is provided for the demo platform-admin account.
- **Functional demo spine:** PASS after installing current Playwright Chromium cache.
- **Release/customer pilot:** NO-GO. Full FE baseline remains red; backend role-boundary live smoke has environment/test-harness 403 errors when run inside container; Keycloak email verification is still production-blocking.
- **Public hostname caveat:** `https://fe.silvergem.org` remains FAIL/502; do not use as demo URL.

## Environment evidence

Raw snapshot: `raw/env-snapshot.txt`

- Docker services: backend, frontend, Keycloak, Postgres, Redis, Qdrant all running/healthy.
- Local frontend landing: HTTP 200.
- Backend health: HTTP 200.
- `https://dev-web.silvergem.org/landing`: HTTP 200.
- `https://fe.silvergem.org/`: HTTP 502.
- Working tree was already dirty before this QA pass; QA added this report/evidence under `docs/qa/2026-09-04-aminra-baseline-admin-functional/`.

## Acceptance matrix

### A1 — Test baseline triage

Status: PARTIAL / FAILING BASELINE IDENTIFIED

Evidence:
- FE full Vitest: `raw/fe-vitest-full.log`
- Backend focused P0: `raw/be-focused-p0.log`
- Backend full collected subset: `raw/be-pytest-full.log`

Results:
- FE Vitest: **181 passed / 19 failed / 200 total**, plus **10 unhandled errors**.
- Backend focused P0/security suite: **135 passed**.
- Backend full current container testpaths: **153 passed / 12 errors / 165 collected**.

Classification:
- FE failures are mostly stale or post-Keycloak behavior mismatches:
  - `auth-oidc`: expected redirect args missing current `extraQueryParams.prompt=login`; signout fallback expectation also stale vs hardened behavior.
  - `forgot-password` and `reset-password`: tests still assume old in-app reset forms/APIs; current behavior redirects to Keycloak flow.
  - `data-export`: tests appear to rely on old auth-token storage shape; rendered page reports no auth token.
  - `SimpleHeader`: branding expectation stale after image wordmark/nav color change.
  - `revision-panel`: empty/error state tests render empty body; needs component/fixture root-cause pass.
- Backend focused P0 coverage is green.
- Backend role-boundary live smoke errors are at token setup (`HTTP 403`) when run inside the backend container against Keycloak token endpoint, while host-level `pre_demo_check.sh` obtains tokens successfully. Likely test-harness/network/Keycloak URL/env mismatch rather than proven app auth failure; needs test harness fix before counting as release-green.

### A2 — Admin smoke Flow 18-20

Status: PASS for covered read endpoints; Flow 19 not independently covered by current script.

Evidence:
- Without admin env: `raw/pre-demo-check-localhost.log` → PASS 32 / WARN 1 / FAIL 0; admin skipped.
- With explicit demo admin password supplied via env: `raw/pre-demo-check-admin-default-pw.log` → PASS 34 / WARN 0 / FAIL 0.

Result:
- Flow 18 Admin analytics endpoint: PASS.
- Flow 20 Overdue submissions queue: PASS.
- Flow 19: not separately asserted by `scripts/pre_demo_check.sh`; current script only labels Flow 18-20 but directly checks 18 and 20.

### A3 — Functional testing / demo spine

Status: PASS on controlled sandbox path.

Evidence:
- Runtime smoke canonical demo URL: `raw/runtime-smoke-localhost-devweb.log` → PASS 12 / WARN 0 / FAIL 0.
- Runtime smoke with known-bad hostname: `raw/runtime-smoke-with-fe-hostname.log` → PASS 12 / FAIL 1 due `fe.silvergem.org` 502.
- Playwright first run: `raw/fe-playwright-demo-spine.log` failed one browser test because Chromium cache was missing.
- Playwright dependency install: `raw/playwright-install-chromium.log`.
- Playwright rerun: `raw/fe-playwright-demo-spine-rerun.log` → **3 passed**.

Functional coverage executed:
- Anonymous public pages and public APIs render safe demo data.
- Business token reaches protected demo-spine endpoints.
- Provider token reaches provider demo-spine endpoints.
- Business token is denied provider-only certificate issuance.
- Public verify page screenshot captured.

Screenshots:
- `evidence/screenshots/TC-FUNC-001_landing-localhost.png`
- `evidence/screenshots/TC-FUNC-002_public-verify-demo-cert.png`
- `evidence/screenshots/TC-FUNC-003_landing-dev-web.png`

### A4 — Keycloak email verification readiness

Status: FAIL / PRODUCTION BLOCKER

Evidence: `raw/keycloak-email-config-check.log`

Findings:
- `verifyEmail` is not enabled.
- SMTP host missing.
- SMTP from missing.
- SMTP transport security not enabled.
- Script verdict: 4 blockers.

## Defects / blockers

### P0 — Production/customer onboarding blocked by Keycloak email config

- Evidence: `raw/keycloak-email-config-check.log`
- Impact: real users cannot safely self-register with verified email; current demo bypass is not production-safe.
- Recommended fix: configure verified-domain SMTP/Resend; send live verification email; re-enable `verifyEmail=true`; rerun `scripts/keycloak-email-config-check.sh`.

### P0 — Full FE baseline red

- Evidence: `raw/fe-vitest-full.log`
- Impact: cannot claim release-clean frontend baseline.
- Recommended fix: triage stale Keycloak-era tests separately from real component failures; update tests through TDD/source-contract discipline before touching production code.

### P1 — Backend role-boundary test harness red inside container

- Evidence: `raw/be-pytest-full.log`, `raw/be-role-boundaries-live-smoke-keycloak-public.log`
- Impact: cannot count full live role matrix green from pytest container run.
- Recommended fix: align `KEYCLOAK_URL`/network path and token fixture with the working host `pre_demo_check.sh` path, then rerun. Do not weaken assertions.

### P1 — `fe.silvergem.org` 502

- Evidence: `raw/runtime-smoke-with-fe-hostname.log`
- Impact: wrong demo URL fails publicly.
- Recommended fix: either fix tunnel/hostname mapping or remove `fe.silvergem.org` from AMINRA demo docs until ownership is clarified.

### P2 — Flow 19 gap in admin smoke script

- Evidence: `scripts/pre_demo_check.sh` directly checks Flow 18 analytics and Flow 20 overdue queue; no separate Flow 19 assertion found in current run.
- Impact: admin smoke label overstates coverage.
- Recommended fix: add explicit Flow 19 endpoint/page check once the intended Flow 19 acceptance criterion is confirmed.

## Test data / mutations

- No new business records intentionally created.
- Playwright browser cache installed under user cache via `npx playwright install chromium`.
- QA evidence files created under this report directory.

## Final recommendation

Proceed with a controlled sandbox demo only if using `localhost:3100` or `dev-web.silvergem.org`, deterministic demo users, and no real customer documents. Do not present AMINRA as customer-pilot ready until Keycloak email verification, FE baseline, backend role-boundary harness, and `fe.silvergem.org` hostname issue are resolved.
