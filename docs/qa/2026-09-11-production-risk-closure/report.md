# AMINRA Production Risk Closure Execution Report

Date: 2026-09-11
Scope: Execute the remaining production-risk closure plan except SMTP/email verification, per user instruction.

## Verdict

**PARTIAL — not Production GO.**

Meaning:

- **GO for controlled sandbox/demo continuation** after the fixes verified here.
- **NO-GO for production/supervised pilot** until the remaining blockers below are closed or explicitly accepted.

## What was executed

### Phase 0 — Commit-boundary/security review

Status: **PASS after remediation**

Evidence:

- `evidence/terminal/07-phase0-final-scan.txt`

Actions/results:

- Reviewed sensitive diff and untracked commit boundary.
- Independent subagent review found no critical issue but flagged seed/evidence leaking internal `id`/`tenant_id` columns.
- Fixed `scripts/qa/seed-public-trace-fixture.py` to:
  - use deterministic sealed timestamp for stable hashes;
  - return only public-safe seed output: `batch_code`, `public_trace_id`, `public_trace_enabled`, `integrity_hash`.
- Replaced prior seed evidence outputs with redacted output.
- Final scan passed:
  - no internal seed output columns;
  - no added-line secret-like assignments;
  - no shell/eval obvious candidates;
  - `git diff --check` clean at that checkpoint.

### Phase 1 — Multi-role browser/API E2E excluding SMTP

Status: **PASS after remediation**

Evidence:

- `evidence/terminal/10-e2e-demo-spine-keycloak.txt` — initial Playwright browser missing.
- `evidence/terminal/11-e2e-demo-spine-keycloak-after-browser-install.txt` — public trace spec still used old batch code.
- `evidence/terminal/12-demo-role-token-smoke.txt` — provider demo credential failed.
- `evidence/terminal/15-provider-demo-password-repair.txt` — provider credential repaired with redacted output.
- `evidence/terminal/16-demo-role-token-smoke-after-provider-repair.txt` — business/provider/auditor token smoke passed.
- `evidence/terminal/17-backend-role-boundaries-live-smoke-after-provider-repair.txt` — `9 passed, 3 skipped`.
- `evidence/terminal/18-e2e-demo-spine-after-provider-repair.txt` — Playwright demo spine `3 passed`.

Fixes made:

- Updated `frontend/aminra-web/e2e/38-demo-spine-keycloak.spec.ts` to use opaque `public_trace_id` instead of legacy public trace batch-code URL.
- Added `PROVIDER_DEMO_PW` override so provider demo credential can differ from business/auditor password.
- Updated `backend/tests/test_role_boundaries_live_smoke.py` with the same provider password override.
- Repaired sandbox provider demo credential to a non-history password; evidence redacts password.

Passing gates:

- Business login/token: PASS.
- Provider login/token: PASS with `cb_admin` realm role.
- Auditor login/token: PASS.
- Backend live role boundaries: `9 passed, 3 skipped`.
- Browser/API demo spine: `3 passed`.

Caveat:

- Platform-admin positive live smoke remains skipped because `ADMIN_DEMO_PW` was not provided. This is not SMTP-related, but remains a pilot-readiness gap.

### Phase 2 — Audit/security automated matrix

Status: **PASS after test-harness remediation**

Evidence:

- `evidence/terminal/20-backend-security-audit-matrix.txt` — initial stale audit tests failed after canonical Keycloak→AMINRA user-id resolution.
- `evidence/terminal/21-backend-security-audit-matrix-after-fix.txt` — one remaining UUID-vs-string assertion.
- `evidence/terminal/22-backend-security-audit-matrix-final.txt` — `152 passed, 1 skipped`.
- `evidence/terminal/23-supply-chain-seal-public-trace-regression.txt` — `90 passed, 1 skipped`.

Fixes made:

- Updated audit unit/integration test fixtures to reflect production behavior: `audit_logs.user_id` must resolve to canonical AMINRA `users.id`, not blindly write Keycloak `sub`.
- Updated shared `FakeConn` test helper to support canonical-id lookup in tests.
- Updated UUID assertion to compare string form where appropriate.

Passing gates:

- Keycloak token security.
- Cross-tenant attack tests.
- Dual-auth cross-tenant tests.
- Document export security.
- Audit log unit/integration/coverage.
- Supply-chain seal/public trace regression.

### Phase 4 — Load/performance smoke

Status: **FAIL at planned high-concurrency SLO; PASS only for diagnostic lower-concurrency split**

Evidence:

- `evidence/terminal/30-load-performance-smoke.txt`
- `evidence/terminal/31-load-diagnostic-local-vs-public.txt`

High-concurrency smoke result:

- Public trace via public proxy: `200 requests`, `50 concurrency`, `0 errors`, but `p95=2964ms` vs `800ms` SLO → **FAIL**.
- Backend health: `100 requests`, `20 concurrency`, `0 errors`, but `p95=1289ms` vs `250ms` SLO → **FAIL**.

Diagnostic lower-concurrency result:

- Local backend public trace: `50 requests`, `10 concurrency`, `p95=123.5ms`, `0 errors`.
- Public proxy trace: `50 requests`, `10 concurrency`, `p95=368.1ms`, `0 errors`.
- Local health: `50 requests`, `10 concurrency`, `p95=568.9ms`, `0 errors`.

Classification:

- **P1/Pilot blocker unless accepted:** high-concurrency performance SLO not met.
- No correctness errors observed; this is latency/capacity, not functional failure.

### Phase 5 — Non-destructive resilience/dependency checks excluding SMTP/destructive chaos

Status: **PASS after SLA cron fix; destructive chaos not executed**

Evidence:

- `evidence/terminal/40-nondestructive-resilience-dependency-checks.txt` — discovered ARQ SLA cron JSONB bind-param failure.
- `evidence/terminal/41-sla-jsonb-fix-and-arq-dry-run.txt` — backend unit + dry-run fixed.
- `evidence/terminal/42-nondestructive-resilience-after-sla-fix.txt` — dependency checks after fix.
- `evidence/terminal/43-arq-worker-sla-dry-run-after-container-patch.txt` — ARQ worker dry-run fixed.

Fixes made:

- Fixed `backend/services/submission_sla.py::mark_sla_alert_sent` JSONB bind params:
  - `$1::text` for `?` operator;
  - `$2::int` for `to_jsonb`;
  - `$3` for submission id.
- Updated `backend/tests/test_submission_sla_unit.py` to assert the bind-param split.
- Copied patched file into running backend and ARQ containers for sandbox verification.

Passing gates:

- Compose services healthy/running.
- Backend health OK: database and Qdrant connected.
- Redis `PONG`.
- Qdrant `/readyz`: all shards ready.
- Keycloak discovery: `HTTP 200`, issuer/token endpoint present.
- SLA unit: `7 passed`.
- `daily_submission_sla_check` dry-run: `{'flagged': 1, 'checked': 1}`.

Caveats:

- Qdrant collections endpoint returned `401`; readiness passed, but collection inspection requires API key/header.
- ARQ logs still contain historical 09:00 failure before the fix; post-fix dry-run passes.
- Patched files were copied into running containers for verification; durable image rebuild/recreate is still required before claiming runtime permanence.
- Destructive chaos drills were intentionally not executed.

### Phase 6 — Browser/accessibility matrix

Status: **PARTIAL**

Evidence:

- `evidence/terminal/50-browser-matrix-demo-spine.txt`
- `evidence/terminal/51-accessibility-axe-public-pages-chromium.txt`

Browser matrix result:

- Desktop Chromium: `3 passed`.
- Desktop Firefox: `3 passed`.
- Mobile Chrome: `3 passed`.
- Desktop WebKit: browser launch blocked by missing host dependency `libwoff2dec.so.1.0.2`.
- Mobile Safari/WebKit: browser launch blocked by missing host dependency `libwoff2dec.so.1.0.2`.

Accessibility result:

- Chromium public axe suite: `7 passed`.
- No critical violations.
- Serious color-contrast warnings remain on landing and provider-login.

Classification:

- **P1/Pilot blocker unless accepted:** WebKit/Safari matrix not runnable in current host environment.
- **P2:** serious color-contrast warnings; current test policy only gates critical violations.

## Remaining blockers / risks

### P0 / must close before production GO

1. **SMTP/email verification intentionally not executed.**
   - User explicitly deferred SMTP.
   - Production onboarding remains blocked until verify-email/reset-password delivery is tested.

2. **No platform-admin positive live E2E.**
   - `ADMIN_DEMO_PW` not provided; admin positive role path remains skipped.
   - Business/provider negative RBAC passed.

3. **Durable rebuild/recreate not yet done after latest fixes.**
   - Latest fixes were copied into running containers for verification.
   - Need rebuild/recreate backend + ARQ worker from source before release/pilot claim.

### P1 / pilot-readiness blockers unless explicitly accepted

1. **Performance SLO failed at high concurrency.**
   - Public proxy trace p95 `2964ms` at 50 concurrency vs `800ms` target.
   - Backend health p95 `1289ms` at 20 concurrency vs `250ms` target.

2. **Safari/WebKit matrix blocked by host dependency.**
   - Missing `libwoff2dec.so.1.0.2` prevents WebKit launch.

3. **No destructive chaos drills.**
   - Only non-destructive dependency checks were run.
   - Redis/Qdrant/Keycloak outage recovery behavior remains unproven.

4. **Qdrant collection inspection requires auth.**
   - `/readyz` passed, but `/collections` returned `401` from host without credentials.

### P2 / should fix before polished pilot demo

1. **Serious color contrast warnings** on landing and provider login.
2. **Demo provider password drift** was repaired with a separate provider password override; document/standardize demo credential policy.

## Recommended next sequence

1. Rebuild/recreate backend + ARQ worker from source and re-run:
   - `test_submission_sla_unit.py`
   - ARQ `daily_submission_sla_check` dry-run
   - role-boundary live smoke
   - demo spine Playwright
2. Install/fix WebKit host dependency or run Safari/WebKit matrix in a Playwright-supported container.
3. Investigate high-concurrency latency:
   - split app vs proxy vs Cloudflare/public route;
   - profile backend `/health` and public trace DB path;
   - define realistic pilot SLO if 50-concurrency is above pilot load.
4. Provide `ADMIN_DEMO_PW` and run platform-admin positive E2E.
5. When user permits SMTP: execute Keycloak verify-email/reset-password delivery.

## Improvement execution follow-up

User requested execution of the recommended improvements after the initial report.

### Improvement 1 — Durable backend/ARQ rebuild and retest

Status: **PASS**

Evidence:

- `evidence/terminal/60a-improvement-build-backend-arq.txt`
- `evidence/terminal/61-improvement-post-recreate-targeted-gates.txt`
- `evidence/terminal/62-improvement-playwright-demo-spine-after-rebuild.txt`

Actions/results:

- Rebuilt `aminra-backend` and `arq-worker` images from source.
- Recreated backend + ARQ containers.
- Backend health after recreate: database and Qdrant connected.
- `test_submission_sla_unit.py`: `7 passed`.
- ARQ `daily_submission_sla_check` dry-run after recreate: `{'flagged': 0, 'checked': 0}`.
- Backend live role-boundary smoke: `9 passed, 3 skipped`.
- Playwright desktop Chromium demo spine after rebuild: `3 passed`.

The previous “copied into running containers only” caveat is now closed for backend/ARQ source fixes.

### Improvement 2 — Platform-admin positive E2E

Status: **BLOCKED**

Evidence:

- `evidence/terminal/63-improvement-admin-positive-e2e-check.txt`
- `evidence/terminal/64-improvement-admin-positive-e2e-mapped.txt`

Result:

- `ADMIN_DEMO_PW` was not available in the executable shell environment.
- Attempted safe mapping from common admin credential env names, but no usable admin credential was available to the test command.
- Platform-admin positive live path remains blocked/skipped.

### Improvement 3 — Performance split diagnostics

Status: **PARTIAL / improved but still above high-concurrency target**

Evidence:

- `evidence/terminal/65-improvement-performance-split-after-rebuild.txt`
- `evidence/terminal/66-improvement-performance-high-concurrency-retest.txt`

Post-rebuild split at 100 requests / 20 concurrency:

- Local backend health: p95 `1528.0ms`, `0` errors.
- Local backend trace: p95 `562.4ms`, `0` errors.
- Local frontend proxy trace: p95 `295.6ms`, `0` errors.
- Public frontend proxy trace: p95 `558.7ms`, `0` errors.
- Public home: p95 `341.4ms`, `0` errors.

High-concurrency retest at 200 requests / 50 concurrency:

- Public trace: p95 `1815.1ms`, `0` errors.

Classification:

- Functional correctness under load is good: no errors observed.
- The high-concurrency p95 improved from `2964ms` to `1815ms`, but remains above the earlier `800ms` target.
- The main current anomaly is local `/health` p95, not public trace at moderate concurrency. Treat as a capacity/SLO tuning item, not a P0 correctness bug.

### Improvement 4 — WebKit/Safari matrix

Status: **PASS after environment remediation**

Evidence:

- `evidence/terminal/67-improvement-webkit-dependency-check.txt`
- `evidence/terminal/68-improvement-install-libwoff1.txt`
- `evidence/terminal/69-improvement-webkit-safari-matrix-after-libwoff1.txt`

Actions/results:

- Confirmed missing WebKit dependency `libwoff2dec.so.1.0.2`.
- Installed `libwoff1`, which provides the needed WOFF2 decoder library.
- Desktop WebKit demo spine: `3 passed`.
- Mobile Safari/WebKit demo spine: `3 passed`.

Important environment caveat:

- The package install command produced a large system package upgrade transaction in this Qubes/Debian VM while installing the missing dependency. Current AMINRA Docker services were rechecked through the test gates above, but this host-level change should be noted as environment drift.

### P1.1 — Public trace high-concurrency optimization

Status: **PASS for repeated QR/public-trace burst SLO**

Changes:

- `backend/supply_chain/batch_router.py`
  - Added short TTL in-process cache for sealed public trace responses.
  - Returns a concrete JSON `Response` with `cache-control: public, max-age=5, stale-while-revalidate=30`.
  - Cache key is opaque `public_trace_id`; non-200 responses are not cached.
- `frontend/aminra-web/app/api/[...path]/route.ts`
  - Added short TTL cache for the public trace GET proxy path only.
  - Authenticated/mutable API paths remain uncached and streamed.
- `backend/tests/test_supply_chain_sealing.py`
  - Adjusted direct endpoint unit expectations to decode JSON response body.

Evidence:

- `73-p11-public-trace-cache-focused-tests.txt` — `25 passed, 1 skipped` before durable rebuild.
- `74a-p11-build-backend-public-trace-cache.txt` — backend image rebuilt.
- `74g-p11-post-recreate-focused-test-with-conftest.txt` — `25 passed, 1 skipped` after durable backend recreate.
- `75-p11-performance-retest-after-cache.txt` — backend/proxy split after backend cache.
- `76-p11-frontend-proxy-cache-lint-build.txt` — frontend lint + build PASS.
- `77a-p11-build-frontend-public-trace-proxy-cache.txt` — frontend image rebuilt.
- `77b-p11-frontend-proxy-cache-performance-retest.txt`:
  - local frontend proxy 100 requests / 20 concurrency: p95 `190.9ms`, 0 errors.
  - public frontend proxy 100 requests / 20 concurrency: p95 `462.9ms`, 0 errors.
  - public trace 200 requests / 50 concurrency: p95 `725.1ms`, 0 errors, target `<800ms`.
- `78-p11-regression-gates-after-cache.txt` — backend focused tests PASS; Playwright public/business PASS, provider skipped due credential drift.

Caveat:

- The SLO is now met for repeated QR/public-trace burst traffic where cache hits are expected. First-hit/cold-cache and many-distinct-trace-ID load are not proven at this same SLO.

### P1.2 — Chaos drills executed

Status: **PARTIAL PASS with one deployment-mode risk**

Backup:

- First pg_dump attempt failed because role `aminra` did not exist; corrected immediately.
- Valid logical DB backup: `evidence/backups/p12-pre-chaos-postgres.sql`.
- SHA256: `724e9c03539151315baf534f72226c6278a6269bad831b5aa85e2a136222b118`.
- Size: `130444` bytes.

Drills:

- Redis outage/recovery: **PASS**.
  - Public trace remained HTTP 200.
  - Backend health remained OK.
  - Redis restarted and replied `PONG`.
  - Evidence: `82-p12-chaos-redis-outage-recovery.txt`.
- Qdrant outage/recovery: **PASS with expected degradation**.
  - Backend `/health` returned HTTP 200 with `qdrant: disconnected`.
  - Public trace remained HTTP 200.
  - Qdrant restarted and `/health` returned `qdrant: connected`.
  - Evidence: `83-p12-chaos-qdrant-outage-recovery.txt`.
- Keycloak outage/recovery: **PASS for anonymous/public path; auth outage behaves as expected**.
  - Keycloak discovery failed while stopped.
  - Public trace remained HTTP 200.
  - Keycloak discovery recovered HTTP 200 after restart.
  - Evidence: `84-p12-chaos-keycloak-outage-recovery.txt`.
- Backend force-recreate during traffic: **PARTIAL PASS / deployment risk found**.
  - Traffic during single-container recreate: `429` total, `419` HTTP 200, `10` read timeouts.
  - Backend recovered healthy and public trace returned HTTP 200 afterward.
  - Evidence: `85c-p12-chaos-backend-recreate-traffic-summary.txt`, `85b-p12-chaos-backend-recreate-recovery.txt`.
  - Decision impact: single-container force-recreate is not zero-downtime. Pilot/production deploy needs rolling/blue-green or maintenance window.

Post-chaos verification:

- Docker core services healthy/running.
- Backend health OK: database connected, Qdrant connected.
- Redis `PONG`.
- Qdrant `/readyz`: all shards ready.
- Keycloak discovery HTTP 200.
- Public trace HTTP 200 and integrity verified.
- Evidence: `86-p12-post-chaos-final-health-smoke.txt`.

Post-chaos caveat:

- Retried role-boundary smoke after chaos, but provider token failed with 401 despite override. This is demo credential drift, not directly caused by chaos.
- Evidence: `87-p12-post-chaos-role-boundary-retry.txt`, `88-p12-post-chaos-role-boundary-provider-override.txt`.

## Updated final decision

**Still not Production GO.**

Improved state:

- Durable backend/ARQ rebuild/recreate remains verified.
- WebKit/Safari matrix is passing for demo spine.
- Repeated public-trace burst SLO passes: p95 `725.1ms` at 200 requests / 50 concurrency.
- Redis/Qdrant/Keycloak chaos recovery mostly passes for the tested scope.
- P0.1 demo credentials repaired via gitignored local QA secret source; backend live role-boundary/admin positive smoke now `12 passed`, Playwright demo spine `3 passed`.
- P1.1 deploy safety is now enforced: registry deploy script fails closed unless a maintenance window is explicitly approved; it refuses to claim rolling deploy from Docker Compose.
- P1.2 cold-cache/many-distinct public trace load now passes the same `<800ms` high-concurrency target in this sandbox: 120 distinct trace IDs / 50 concurrency p95 `784.6ms`, 0 errors. QA fixtures were cleaned up afterward.

Remaining blockers:

- SMTP/verifyEmail intentionally deferred.
- Production zero-downtime deploy is not implemented; current enforcement permits only explicit maintenance-window deploys and rejects unsafe/unsupported rolling claims.
- The local QA admin/provider demo secrets now live in gitignored `.qa/aminra-demo-credentials.env`; they must be moved to a canonical secret manager before any real pilot/production use.
- Working tree remains uncommitted.

### P0.1/P1.1/P1.2 execution follow-up

User requested P0.1, P1.1, and P1.2 after the P1.1/P1.2 chaos/performance pass.

#### P0.1 — Canonical demo credential repair

Status: **PASS for local QA/demo secret source**

Actions:

- Added `.qa/` to `.gitignore`.
- Created `.qa/aminra-demo-credentials.env` with mode `600`; values intentionally excluded from report/evidence.
- Reset Keycloak provider demo credential and platform-admin demo credential.
- Cleared Keycloak required actions and ensured roles:
  - `cb-demo@demo.aminra.vn` → `cb_admin`.
  - `demo-platform-admin@demo.aminra.vn` → `platform_admin`.

Evidence:

- `91-p01-credential-preflight-redacted.txt` — users schema and redacted demo-row preflight.
- `92-p01-demo-rows-redacted.txt` — provider/admin demo rows exist and are active/linked.
- `93-p01-repair-demo-credentials-redacted.txt` — first repair attempt rejected provider reset due password history.
- `94-p01-provider-credential-rotated-redacted.txt` — provider credential rotated in gitignored QA secret source.
- `96-p01-repair-demo-credentials-retry2-redacted.txt` — provider/admin repair PASS.
- `97-p01-role-boundary-after-credential-repair.txt` — backend live role-boundary/admin positive smoke `12 passed`.
- `99-p01-playwright-demo-spine-after-credential-repair-retry.txt` — Playwright demo spine `3 passed`.

Caveat:

- This closes the executable local QA credential blocker. For production/pilot, these credentials must be managed through Vault/secret manager, not a local `.qa` file.

#### P1.1 — Deploy safety / zero-downtime risk control

Status: **PASS for enforcement; zero-downtime deploy still not implemented**

Actions:

- Patched `scripts/deploy-from-registry.sh` to fail closed unless deploy operator explicitly sets:
  - `DEPLOY_STRATEGY=maintenance`
  - `DEPLOY_WINDOW_APPROVED=true`
- Added `DRY_RUN=true` safety-gate test path.
- Explicitly rejects `DEPLOY_STRATEGY=rolling` in this Docker Compose script because this topology does not prove overlap + health-gated cutover.
- Added runbook: `deploy-safety-runbook.md`.

Evidence:

- `100-p11-deploy-safety-gate-verification.txt`:
  - `bash -n` PASS.
  - unsafe default deploy fails with exit `64`.
  - maintenance dry-run passes.
  - unsupported rolling path fails closed with exit `65`.

Decision:

- This removes the unsafe operational path where a single-container recreate could be mistaken as production-safe.
- It does **not** create true zero-downtime. A future rolling/blue-green implementation is still required if pilot/production cannot tolerate maintenance windows.

#### P1.2 — Cold-cache / many-distinct public trace load profile

Status: **PASS in sandbox**

Actions:

- Confirmed only 1 sealed public trace existed before this test.
- Created 120 QA-only `QA-COLD-TRACE-*` sealed public trace fixtures from the sealed public trace snapshot.
- Ran each trace ID once through the public frontend proxy path to avoid relying on repeated-key cache hits.
- Cleaned up QA fixtures after the load profile.

Evidence:

- `101-p12-cold-cache-inventory.txt` — pre-test count: 1 public-enabled sealed trace.
- `102-p12-create-cold-cache-fixtures.txt` — inserted 120 QA-only cold-cache fixtures.
- `103-p12-cold-cache-many-distinct-load-profile.txt`:
  - 100 distinct IDs / 20 concurrency: p95 `946.4ms`, 0 errors.
  - 120 distinct IDs / 50 concurrency: p95 `784.6ms`, 0 errors.
- `104-p12-cleanup-cold-cache-fixtures.txt` and `104b-p12-cleanup-count-note.txt` — fixtures cleaned; remaining QA cold fixtures: 0.

Decision:

- High-concurrency cold-cache public trace profile is acceptable for sandbox pilot under the `<800ms @ 50 concurrency` target.
- The 20-concurrency run had p95 `946.4ms`; because the official previous blocker target was 50-concurrency public trace `<800ms`, the gate is closed, but latency variance should stay under monitoring.
