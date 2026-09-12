# AMINRA Customer-Ready Full-System QA Report

Generated: 2026-09-12T07:31:27.485552
Output: 

## Verdict lanes

- sandbox_demo: **FAIL**
- supervised_pilot: **FAIL**
- customer_onboarding: **PARTIAL** — SMTP deferred prevents PASS when deferred.
- production_go: **PARTIAL** — requires SMTP, zero dirty release boundary, accepted load/chaos/deploy gates.

## Summary by domain

- 00-env: PASS=4
- 01-auth-session-rbac: DEFERRED=1, FAIL=5
- 02-tenant-idor-route-boundary: FAIL=1, PASS=1
- 03-supply-chain-trace: FAIL=4
- 04-submission-cert-lifecycle: FAIL=3
- 05-admin-user-crud: FAIL=2
- 06-pdf-doc-versioning: FAIL=3
- 07-jobs-audit-data-security: FAIL=1, PASS=2
- 08-frontend-browser-a11y: FAIL=1, PASS=4
- 09-load-chaos-deploy: DEFERRED=1, FAIL=1, PASS=1

## Detailed results

- **PASS**  — date-and-git-boundary: 
- **PASS**  — docker-compose-health-and-http-smoke: 
- **PASS**  — runtime-smoke-script: 
- **PASS**  — diff-whitespace-check: 
- **FAIL**  — keycloak-token-admin-jwks-dual-auth:  — exit_code=127
- **FAIL**  — role-boundaries-live-and-admin-reset:  — exit_code=127
- **FAIL**  — frontend-auth-focused-vitest:  — exit_code=1
- **FAIL**  — playwright-keycloak-token-login-multiuser:  — exit_code=1
- **FAIL**  — playwright-token-isolation-and-logout:  — exit_code=1
- **DEFERRED**  — smtp-verifyEmail-password-reset-live-send:  — Founder explicitly deferred SMTP. Keep customer_onboarding/production_go non-PASS until RUN_SMTP=1 and live-send passes.
- **FAIL**  — cross-tenant-and-unauth-boundaries:  — exit_code=127
- **PASS**  — route-inventory-unknown-risk-scan: 
- **FAIL**  — supply-chain-core-sealing-eligibility:  — exit_code=127
- **FAIL**  — seed-deterministic-public-trace-fixture:  — exit_code=127
- **FAIL**  — public-trace-valid-invalid-smoke:  — exit_code=2
- **FAIL**  — playwright-supply-chain-and-demo-spine:  — exit_code=1
- **FAIL**  — submission-revisions-sla-and-cert-lifecycle:  — exit_code=127
- **FAIL**  — known-p0-gap-test-file-presence:  — exit_code=2
- **FAIL**  — playwright-cert-and-state-scoring:  — exit_code=1
- **FAIL**  — admin-user-member-auditor-crud:  — exit_code=127
- **FAIL**  — playwright-admin-user-flows:  — exit_code=1
- **FAIL**  — pdf-renderer-document-versioning:  — exit_code=127
- **FAIL**  — pdf-visual-baselines:  — exit_code=127
- **FAIL**  — playwright-template-document-ui:  — exit_code=1
- **FAIL**  — jobs-audit-data-upload:  — exit_code=127
- **PASS**  — high-signal-log-scan: 
- **PASS**  — rate-limit-doc-presence: 
- **PASS**  — frontend-full-vitest: 
- **PASS**  — frontend-lint: 
- **PASS**  — frontend-build: 
- **PASS**  — playwright-accessibility-mobile-critical: 
- **FAIL**  — playwright-full-matrix:  — exit_code=1
- **PASS**  — deploy-safety-gates: 
- **FAIL**  — public-trace-load-profile:  — exit_code=1
- **DEFERRED**  — chaos-drills:  — RUN_CHAOS=0 CHAOS_APPROVED=false. Destructive chaos requires explicit opt-in and backup/recovery checks.

## Required interpretation

-  is not a pass. SMTP/verifyEmail remains a customer-onboarding blocker until explicitly tested.
- Missing P0 lifecycle test files are blockers unless equivalent coverage is mapped with evidence.
- Any FAIL in auth, tenant, supply-chain, lifecycle, or admin identity domains is release-blocking.
- QA-created data cleanup must be verified in the relevant evidence logs before using this report for sign-off.
