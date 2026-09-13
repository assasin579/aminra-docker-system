# AMINRA Customer-Ready Full-System QA Report

Generated: 2026-09-13T01:22:40.229691
Output: `docs/qa/2026-09-12-customer-ready-full-system`
Commit under test: `0667c4d`

## Verdict lanes

- sandbox_demo: **PASS WITH CAUTION** — core functional/browser/security demo path is green, but public edge SLO is red; avoid load-sensitive QR claims.
- supervised_pilot: **PARTIAL** — blocked by public `dev-web` trace p95 SLO failure, SMTP deferred, remaining fixture/data skips, dependency remediation, and chaos not rerun in this pass.
- customer_onboarding: **PARTIAL** — SMTP/verifyEmail/password-reset live-send remains deferred.
- production_go: **NO-GO** — requires SMTP live-send, public edge/cache SLO pass, chaos/recovery evidence, and dependency remediation for direct critical/high production packages.

## Summary by status

- PASS: 35
- WARN: 2
- FAIL: 1
- DEFERRED: 2

## Critical updates from improvement pass

- Full Playwright desktop matrix is now **PASS** after skip triage: `301 passed`, `25 skipped`, `0 failed`.
- Public trace local backend and local frontend proxy load profiles pass 200 requests / 50 concurrency / p95 < 800ms.
- Public `dev-web.silvergem.org` trace profile still **FAILS** p95: `1831.8ms` with `cf-cache-status: DYNAMIC`; local proxy cache marker is `x-aminra-proxy-cache: hit`. This is now classified as **public edge/tunnel/cache configuration risk**, not backend hot-path failure.
- Skipped tests triage completed in `033b-*`: 8 fixture/env skips fixed; full desktop Chromium is now `301 passed`, `25 skipped`, `0 failed`; remaining fixture/data skips are 5 and require seed/config before unsupervised pilot.
- Dependency audit triage completed: frontend npm has direct Next critical/high production blocker; backend pip audit has python-ecdsa via python-jose with lower apparent reachability but auth-sensitive WARN.
- Tenant / IDOR / data-isolation confidence is now **8/10 PASS WITH RESIDUAL WARNINGS**: live-token UAT `50 passed`, P0 anonymous/resource boundary tests `32 passed`, coverage gate `3 passed`, `242` routes inventoried with `240` covered / `2` P1 deferred / `0` deferred P0, and static scan now has `0 HIGH`, `161 MEDIUM`, `8 INFO`. Evidence: `docs/qa/2026-09-13-tenant-idor-confidence-8of10/report.md`.
- SMTP remains intentionally deferred and blocks customer onboarding/production.

## Detailed results

- **PASS** `00-env` — date-and-git-boundary: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/001-00-env-date-and-git-boundary.txt` — previous evidence; git boundary later changed by local commit 0667c4d
- **PASS** `00-env` — docker-compose-health-and-http-smoke: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/002-00-env-docker-compose-health-and-http-smoke.txt` — services healthy during verification
- **PASS** `00-env` — runtime-smoke-script: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/003-00-env-runtime-smoke-script.txt` — previous evidence
- **PASS** `00-env` — diff-whitespace-check: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/004-00-env-diff-whitespace-check.txt` — rerun passed after excluding docs/qa evidence from whitespace gate
- **PASS** `00-env` — repair-demo-keycloak-accounts: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/005-00-env-repair-demo-keycloak-accounts.txt` — redacted .qa credentials only
- **PASS** `01-auth-session-rbac` — keycloak-token-admin-jwks-dual-auth: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/006-01-auth-session-rbac-keycloak-token-admin-jwks-dual-auth.txt`
- **PASS** `01-auth-session-rbac` — role-boundaries-live-and-admin-reset: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/007-01-auth-session-rbac-role-boundaries-live-and-admin-reset.txt`
- **PASS** `01-auth-session-rbac` — frontend-auth-focused-vitest: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/008-01-auth-session-rbac-frontend-auth-focused-vitest.txt`
- **PASS** `01-auth-session-rbac` — playwright-keycloak-token-login-multiuser: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/009-01-auth-session-rbac-playwright-keycloak-token-login-multiuser.txt`
- **PASS** `01-auth-session-rbac` — playwright-token-isolation-and-logout: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/010-01-auth-session-rbac-playwright-token-isolation-and-logout.txt`
- **DEFERRED** `01-auth-session-rbac` — smtp-verifyEmail-password-reset-live-send: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/011-01-auth-session-rbac-smtp-verifyemail-password-reset-live-send-deferred.txt` — Founder explicitly deferred SMTP. Blocks customer_onboarding/production_go.
- **PASS** `02-tenant-idor-route-boundary` — cross-tenant-and-unauth-boundaries: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/012-02-tenant-idor-route-boundary-cross-tenant-and-unauth-boundaries.txt`
- **PASS** `02-tenant-idor-route-boundary` — route-inventory-unknown-risk-scan: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/013-02-tenant-idor-route-boundary-route-inventory-unknown-risk-scan.txt` — representative scan, not formal complete route matrix
- **PASS** `02-tenant-idor-route-boundary` — tenant-idor-confidence-8of10-final: `docs/qa/2026-09-13-tenant-idor-confidence-8of10/report.md` — confidence now 8/10 PASS WITH RESIDUAL WARNINGS; final evidence: live-token UAT 50 passed, P0 anonymous/resource boundaries 32 passed, coverage gate 3 passed, 0 deferred P0 rows, 0 HIGH scanner findings
- **PASS** `03-supply-chain-trace` — supply-chain-core-sealing-eligibility: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/014-03-supply-chain-trace-supply-chain-core-sealing-eligibility.txt`
- **PASS** `03-supply-chain-trace` — seed-deterministic-public-trace-fixture: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/015-03-supply-chain-trace-seed-deterministic-public-trace-fixture.txt`
- **PASS** `03-supply-chain-trace` — public-trace-valid-invalid-smoke: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/016-03-supply-chain-trace-public-trace-valid-invalid-smoke.txt`
- **PASS** `03-supply-chain-trace` — playwright-supply-chain-and-demo-spine: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/017-03-supply-chain-trace-playwright-supply-chain-and-demo-spine.txt`
- **PASS** `04-submission-cert-lifecycle` — submission-revisions-sla-and-cert-lifecycle: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/018-04-submission-cert-lifecycle-submission-revisions-sla-and-cert-lifecycle.txt`
- **PASS** `04-submission-cert-lifecycle` — known-p0-gap-test-file-presence: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/019-04-submission-cert-lifecycle-known-p0-gap-test-file-presence.txt`
- **PASS** `04-submission-cert-lifecycle` — playwright-cert-and-state-scoring: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/020-04-submission-cert-lifecycle-playwright-cert-and-state-scoring.txt` — superseded by full Playwright PASS after Keycloak/data-export fixes
- **PASS** `05-admin-user-crud` — admin-user-member-auditor-crud: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/021-05-admin-user-crud-admin-user-member-auditor-crud.txt`
- **PASS** `05-admin-user-crud` — playwright-admin-user-flows: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/022-05-admin-user-crud-playwright-admin-user-flows.txt`
- **PASS** `06-pdf-doc-versioning` — pdf-renderer-document-versioning: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/023-06-pdf-doc-versioning-pdf-renderer-document-versioning.txt`
- **PASS** `06-pdf-doc-versioning` — template-files-repair-guard: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/024-06-pdf-doc-versioning-template-files-repair-guard.txt`
- **PASS** `06-pdf-doc-versioning` — pdf-visual-baselines: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/025-06-pdf-doc-versioning-pdf-visual-baselines.txt`
- **PASS** `06-pdf-doc-versioning` — playwright-template-document-ui: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/026-06-pdf-doc-versioning-playwright-template-document-ui.txt`
- **PASS** `07-jobs-audit-data-security` — jobs-audit-data-upload: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/027-07-jobs-audit-data-security-jobs-audit-data-upload.txt`
- **PASS** `07-jobs-audit-data-security` — high-signal-log-scan: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/028-07-jobs-audit-data-security-high-signal-log-scan.txt`
- **PASS** `07-jobs-audit-data-security` — rate-limit-doc-presence: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/029-07-jobs-audit-data-security-rate-limit-doc-presence.txt`
- **PASS** `08-frontend-browser-a11y` — frontend-full-vitest: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/030-08-frontend-browser-a11y-frontend-full-vitest.txt`
- **PASS** `08-frontend-browser-a11y` — frontend-lint: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/031-08-frontend-browser-a11y-frontend-lint.txt`
- **PASS** `08-frontend-browser-a11y` — frontend-build: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/032-08-frontend-browser-a11y-frontend-build.txt` — frontend image rebuilt successfully after proxy cache change; npm audit reports dependency vulnerabilities, track separately
- **PASS** `08-frontend-browser-a11y` — playwright-full-matrix: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/033-08-frontend-browser-a11y-playwright-full-matrix.txt` — superseded by skip-triage rerun: 301 passed, 25 skipped, 0 failed on desktop-chromium
- **PASS** `08-frontend-browser-a11y` — playwright-skipped-tests-classification: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/033a-08-frontend-browser-a11y-playwright-skipped-tests-classification.txt` — superseded by targeted triage; remaining skipped tests documented
- **PASS** `08-frontend-browser-a11y` — playwright-skipped-tests-triage-after-fixes: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/033b-08-frontend-browser-a11y-playwright-skipped-tests-triage-after-fixes.txt` — 8 fixture/env skips fixed; final full desktop Chromium: 301 passed, 25 skipped, 0 failed
- **WARN** `10-dependency-audit` — frontend-npm-audit-triage: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/037-10-dependency-audit-frontend-npm-triage.txt` — npm audit has direct Next critical/high production blocker; controlled upgrade required
- **WARN** `10-dependency-audit` — backend-pip-audit-triage: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/038-10-dependency-audit-backend-pip-triage.txt` — ecdsa via python-jose; lower apparent reachability but auth-sensitive WARN
- **PASS** `09-load-chaos-deploy` — deploy-safety-gates: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/034-09-load-chaos-deploy-deploy-safety-gates.txt`
- **FAIL** `09-load-chaos-deploy` — public-trace-load-profile: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/035-09-load-chaos-deploy-public-trace-load-profile.txt` — local backend p95 698.8ms PASS; local frontend p95 686.5ms PASS; public dev-web p95 1831.8ms FAIL, cf-cache-status DYNAMIC
- **DEFERRED** `09-load-chaos-deploy` — chaos-drills: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/036-09-load-chaos-deploy-chaos-drills-deferred.txt` — Destructive chaos requires explicit opt-in and backup/recovery checks

## Required interpretation

- `DEFERRED` is not a pass. SMTP/verifyEmail remains a customer-onboarding blocker until explicitly tested.
- Public trace local/proxy hot path is acceptable, but the public Cloudflare/tunnel path is not meeting the 800ms p95 SLO. Do not present QR/public trace as production-load-ready until CF cache status is HIT/eligible or the tunnel/fronting architecture is changed.
- Full Playwright PASS materially improves functional confidence. The fixture/env skip risk has been reduced from 13 to 5; remaining data/config skips are WARN until deterministic seed/setup is added.
- Tenant/IDOR 8/10 is scoped to route/auth/data-isolation evidence only; it does not override public edge/CDN SLO failure, SMTP/customer-onboarding blocker, or dependency audit WARN.
- Evidence is source-of-truth only for this commit and this environment; do not extrapolate to production infra without matching edge/CDN/SMTP/secret-manager configuration.

## 2026-09-13 skip/dependency triage addendum

- Targeted fixture/env triage converted 8 previously skipped tests to executable PASS by removing retired `/api/auth/login` dependency and using Keycloak token helpers.
- Remaining skips: 7 SMTP-deferred + 1 explicit SMTP Keycloak reset marker, 12 mobile/tablet project-gated, 5 environment/data/config-dependent.
- Dependency audit triage is not remediation: production remains NO-GO until direct Next critical/high advisories are upgraded or formally risk-accepted with compensating controls.
## 2026-09-13 SMTP + Edge/CDN rerun addendum

- SMTP/verifyEmail QA live-send is now **PASS for internal QA relay**: Keycloak accepted `VERIFY_EMAIL` execute-actions-email and the SMTP capture relay logged `SMTP_CAPTURE_BEGIN`/`SMTP_CAPTURE_END`. Evidence: `docs/qa/2026-09-13-smtp-live/report.md`. This does **not** equal production SMTP readiness because the QA relay is non-TLS/non-auth internal-only.
- Public edge/CDN trace SLO remains **FAIL/BLOCKED**: latest split run shows local backend p95 `419.7ms` PASS, local frontend proxy p95 `427.3ms` PASS, public dev-web p95 `957.8ms` FAIL with `cf-cache-status: DYNAMIC`. Evidence: `docs/qa/2026-09-13-edge-cdn-fix/report.md`.
- A Cloudflare cache-rule apply script was created at `scripts/qa/apply-cloudflare-public-trace-cache-rule.sh`, but it was not applied because Cloudflare API token/zone ID or IaC config were unavailable in this session.
