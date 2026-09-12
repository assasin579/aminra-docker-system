# AMINRA Customer-Ready Full-System QA Report

Generated: 2026-09-12T10:41:12.800777
Output: `docs/qa/2026-09-12-improvement-follow-up-critical`

## Verdict lanes

- sandbox_demo: **PASS**
- supervised_pilot: **PARTIAL**
- customer_onboarding: **PARTIAL** — SMTP deferred prevents PASS when deferred.
- production_go: **PARTIAL** — requires SMTP, zero dirty release boundary, accepted load/chaos/deploy gates.

## Summary by domain

- 00-env: PASS=4
- 01-auth-session-rbac: DEFERRED=1, PASS=5
- 02-tenant-idor-route-boundary: PASS=2
- 03-supply-chain-trace: PASS=4
- 04-submission-cert-lifecycle: PASS=3
- 05-admin-user-crud: PASS=2
- 06-pdf-doc-versioning: DEFERRED=1, PASS=3
- 07-jobs-audit-data-security: PASS=3
- 08-frontend-browser-a11y: DEFERRED=1, PASS=4
- 09-load-chaos-deploy: DEFERRED=1, FAIL=1, PASS=1

## Detailed results

- **PASS** `00-env` — date-and-git-boundary: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/001-00-env-date-and-git-boundary.txt`
- **PASS** `00-env` — docker-compose-health-and-http-smoke: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/002-00-env-docker-compose-health-and-http-smoke.txt`
- **PASS** `00-env` — runtime-smoke-script: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/003-00-env-runtime-smoke-script.txt`
- **PASS** `00-env` — diff-whitespace-check: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/004-00-env-diff-whitespace-check.txt`
- **PASS** `01-auth-session-rbac` — keycloak-token-admin-jwks-dual-auth: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/005-01-auth-session-rbac-keycloak-token-admin-jwks-dual-auth.txt`
- **PASS** `01-auth-session-rbac` — role-boundaries-live-and-admin-reset: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/006-01-auth-session-rbac-role-boundaries-live-and-admin-reset.txt`
- **PASS** `01-auth-session-rbac` — frontend-auth-focused-vitest: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/007-01-auth-session-rbac-frontend-auth-focused-vitest.txt`
- **PASS** `01-auth-session-rbac` — playwright-keycloak-token-login-multiuser: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/008-01-auth-session-rbac-playwright-keycloak-token-login-multiuser.txt`
- **PASS** `01-auth-session-rbac` — playwright-token-isolation-and-logout: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/009-01-auth-session-rbac-playwright-token-isolation-and-logout.txt`
- **DEFERRED** `01-auth-session-rbac` — smtp-verifyEmail-password-reset-live-send: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/010-01-auth-session-rbac-smtp-verifyemail-password-reset-live-send-deferred.txt` — Founder explicitly deferred SMTP. Keep customer_onboarding/production_go non-PASS until RUN_SMTP=1 and live-send passes.
- **PASS** `02-tenant-idor-route-boundary` — cross-tenant-and-unauth-boundaries: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/011-02-tenant-idor-route-boundary-cross-tenant-and-unauth-boundaries.txt`
- **PASS** `02-tenant-idor-route-boundary` — route-inventory-unknown-risk-scan: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/012-02-tenant-idor-route-boundary-route-inventory-unknown-risk-scan.txt`
- **PASS** `03-supply-chain-trace` — supply-chain-core-sealing-eligibility: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/013-03-supply-chain-trace-supply-chain-core-sealing-eligibility.txt`
- **PASS** `03-supply-chain-trace` — seed-deterministic-public-trace-fixture: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/014-03-supply-chain-trace-seed-deterministic-public-trace-fixture.txt`
- **PASS** `03-supply-chain-trace` — public-trace-valid-invalid-smoke: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/015-03-supply-chain-trace-public-trace-valid-invalid-smoke.txt`
- **PASS** `03-supply-chain-trace` — playwright-supply-chain-and-demo-spine: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/016-03-supply-chain-trace-playwright-supply-chain-and-demo-spine.txt`
- **PASS** `04-submission-cert-lifecycle` — submission-revisions-sla-and-cert-lifecycle: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/017-04-submission-cert-lifecycle-submission-revisions-sla-and-cert-lifecycle.txt`
- **PASS** `04-submission-cert-lifecycle` — known-p0-gap-test-file-presence: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/018-04-submission-cert-lifecycle-known-p0-gap-test-file-presence.txt`
- **PASS** `04-submission-cert-lifecycle` — playwright-cert-and-state-scoring: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/019-04-submission-cert-lifecycle-playwright-cert-and-state-scoring.txt`
- **PASS** `05-admin-user-crud` — admin-user-member-auditor-crud: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/020-05-admin-user-crud-admin-user-member-auditor-crud.txt`
- **PASS** `05-admin-user-crud` — playwright-admin-user-flows: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/021-05-admin-user-crud-playwright-admin-user-flows.txt`
- **PASS** `06-pdf-doc-versioning` — pdf-renderer-document-versioning: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/022-06-pdf-doc-versioning-pdf-renderer-document-versioning.txt`
- **PASS** `06-pdf-doc-versioning` — template-files-repair-guard: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/023-06-pdf-doc-versioning-template-files-repair-guard.txt`
- **DEFERRED** `06-pdf-doc-versioning` — pdf-visual-baselines: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/024-06-pdf-doc-versioning-pdf-visual-baselines-deferred.txt` — RUN_VISUAL=0. Run with RUN_VISUAL=1 for visual baseline validation.
- **PASS** `06-pdf-doc-versioning` — playwright-template-document-ui: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/025-06-pdf-doc-versioning-playwright-template-document-ui.txt`
- **PASS** `07-jobs-audit-data-security` — jobs-audit-data-upload: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/026-07-jobs-audit-data-security-jobs-audit-data-upload.txt`
- **PASS** `07-jobs-audit-data-security` — high-signal-log-scan: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/027-07-jobs-audit-data-security-high-signal-log-scan.txt`
- **PASS** `07-jobs-audit-data-security` — rate-limit-doc-presence: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/028-07-jobs-audit-data-security-rate-limit-doc-presence.txt`
- **PASS** `08-frontend-browser-a11y` — frontend-full-vitest: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/029-08-frontend-browser-a11y-frontend-full-vitest.txt`
- **PASS** `08-frontend-browser-a11y` — frontend-lint: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/030-08-frontend-browser-a11y-frontend-lint.txt`
- **PASS** `08-frontend-browser-a11y` — frontend-build: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/031-08-frontend-browser-a11y-frontend-build.txt`
- **PASS** `08-frontend-browser-a11y` — playwright-accessibility-mobile-critical: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/032-08-frontend-browser-a11y-playwright-accessibility-mobile-critical.txt`
- **DEFERRED** `08-frontend-browser-a11y` — playwright-full-matrix: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/033-08-frontend-browser-a11y-playwright-full-matrix-deferred.txt` — RUN_FULL_E2E=0. Focused critical Playwright set ran; full matrix deferred.
- **PASS** `09-load-chaos-deploy` — deploy-safety-gates: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/034-09-load-chaos-deploy-deploy-safety-gates.txt`
- **FAIL** `09-load-chaos-deploy` — public-trace-load-profile: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/035-09-load-chaos-deploy-public-trace-load-profile.txt` — exit_code=1
- **DEFERRED** `09-load-chaos-deploy` — chaos-drills: `docs/qa/2026-09-12-improvement-follow-up-critical/evidence/terminal/036-09-load-chaos-deploy-chaos-drills-deferred.txt` — RUN_CHAOS=0 CHAOS_APPROVED=false. Destructive chaos requires explicit opt-in and backup/recovery checks.

## Required interpretation

- `DEFERRED` is not a pass. SMTP/verifyEmail remains a customer-onboarding blocker until explicitly tested.
- Missing P0 lifecycle test files are blockers unless equivalent coverage is mapped with evidence.
- Any FAIL in auth, tenant, supply-chain, lifecycle, or admin identity domains is release-blocking.
- QA-created data cleanup must be verified in the relevant evidence logs before using this report for sign-off.
