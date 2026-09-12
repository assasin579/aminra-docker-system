# AMINRA Customer-Ready Full-System QA Test Plan

Date: 2026-09-12  
Owner: Senior QA / DevSecOps  
Repo: `/home/user/Documents/aminra-docker-system`  
Canonical sandbox URL: `https://dev-web.silvergem.org`  
SMTP status: **INTENTIONALLY DEFERRED by founder** — keep visible as `DEFERRED`, never mark PASS.

## 0. Executive verdict model

This plan does **not** allow a single vague “all tests passed” verdict. Every run must produce separate lane verdicts:

- `sandbox_demo`: controlled demo readiness.
- `supervised_pilot`: friendly pilot readiness with operator present.
- `customer_onboarding`: real customer self-use readiness.
- `production_go`: production readiness.

Allowed statuses:

- `PASS` — all required gates for that lane passed with evidence.
- `PARTIAL` — meaningful coverage passed, but at least one required gate is missing/deferred/ambiguous.
- `BLOCKED` — prerequisite missing: credentials, environment, fixture, approval.
- `FAIL` — invariant failed.
- `DEFERRED` — intentionally out of scope by explicit decision; must remain visible.

Current expected top-level policy:

- SMTP/verifyEmail is `DEFERRED`, therefore `customer_onboarding` and `production_go` cannot be `PASS`.
- Controlled sandbox demo may pass if auth/session, role-boundary, public trace, runtime smoke, and demo spine pass.

---

## 1. Test objectives

Prove AMINRA across **all functional/risk domains**, not just happy paths:

1. Auth / Keycloak / session / logout / account switch.
2. Tenant isolation / IDOR / route boundary.
3. Supply-chain traceability / public QR / sealed snapshot.
4. Supplier/NCC eligibility / CB authority.
5. Submission lifecycle / certification lifecycle.
6. Admin/user/member/auditor CRUD and Keycloak↔Postgres consistency.
7. PDF/document rendering/versioning/official artifacts.
8. Async jobs / ARQ / compliance workers / observability.
9. Frontend critical contracts / FE→BE error handling / build/lint.
10. Browser E2E / mobile / accessibility / visual smoke.
11. Load/performance / cache / public trace SLO.
12. Resilience/chaos/deploy safety.
13. Data export/deletion / audit logs / rate limit / upload path safety.
14. SMTP/verifyEmail — tracked but deferred.

---

## 2. Execution artifacts

Runner script:

```text
scripts/qa/run-customer-ready-full-system-qa.sh
```

Default report output:

```text
docs/qa/YYYY-MM-DD-customer-ready-full-system/report.md
docs/qa/YYYY-MM-DD-customer-ready-full-system/evidence/terminal/*.txt
docs/qa/YYYY-MM-DD-customer-ready-full-system/evidence/raw/*.json
```

The runner must continue after failures so we get a complete risk map, not a first-failure-only result.

---

## 3. Environment and safety rules

### Required prerequisites

- Docker Compose stack available.
- Backend container service: `aminra-backend`.
- Frontend app path: `frontend/aminra-web`.
- Keycloak sandbox accounts/credentials supplied via environment or gitignored `.qa/aminra-demo-credentials.env`.
- No secrets printed to terminal or report.

### Safety switches

Default run is non-destructive except QA-prefixed fixture creation/cleanup used by existing scripts.

Optional gates require explicit opt-in:

```bash
RUN_LOAD=1      # run load/performance profiles
RUN_CHAOS=1     # run destructive dependency outage drills
RUN_VISUAL=1    # run PDF/browser visual suites if supported
RUN_FULL_E2E=1  # run broad Playwright matrix instead of focused critical set
RUN_SMTP=0      # must remain 0 until founder re-enables SMTP testing
```

If `RUN_CHAOS=1`, the operator must confirm backup/recovery probes exist before execution.

---

## 4. Risk-domain matrix

### P0-1. Auth / Keycloak / Session / Email

**Invariants**

- Every canonical role can authenticate only when enabled and credential-valid.
- `/auth/me` returns correct app identity, tenant, role, owner/sub-role flags, and preserved raw realm roles where admin guards need them.
- Logout/account-switch cannot resurrect stale browser identity.
- Password reset revokes sessions.
- SMTP/verifyEmail remains visible as deferred until explicitly enabled.

**Automated evidence**

- `backend/tests/test_keycloak_token_security.py`
- `backend/tests/test_keycloak_admin_edge.py`
- `backend/tests/test_keycloak_jwks_edge.py`
- `backend/tests/test_dual_auth_unit.py`
- `backend/tests/test_dual_auth_fast_path.py`
- `backend/tests/test_dual_auth_cross_tenant_unit.py`
- `backend/tests/test_role_boundaries_live_smoke.py`
- `backend/tests/test_admin_user_password_reset.py`
- `backend/tests/test_demo_account_login_smoke_script.py`
- `frontend/aminra-web/e2e/keycloak/*.spec.ts`
- `frontend/aminra-web/e2e/22-token-isolation.spec.ts`
- `frontend/aminra-web/e2e/23-cross-context-logout.spec.ts`
- `frontend/aminra-web/e2e/38-demo-spine-keycloak.spec.ts`

**Required manual/UAT cases if not automated**

- Browser account switch: business → logout confirmation → platform admin; verify avatar/sidebar/auth-me.
- Multi-tab logout propagation.
- Expired/invalid token handling.
- SMTP verification/password reset: **DEFERRED**.

---

### P0-2. Tenant Isolation / IDOR / Route Boundary

**Invariants**

- Tenant A cannot read or mutate Tenant B resources.
- High-risk invalid IDs return 404/403 without existence leak or private metadata.
- Anonymous access is denied except explicitly public routes.

**Automated evidence**

- `backend/tests/test_keycloak_cross_tenant_attack.py`
- `backend/tests/test_dual_auth_cross_tenant_unit.py`
- `backend/tests/test_unauth_route_boundaries.py`
- `backend/tests/test_certificate_pdf_integrity_smoke.py`
- `backend/tests/test_generate_document_export_security.py`
- `backend/tests/test_kc_sub_fk_smoke.py`
- `backend/tests/uat/test_uat_c_tenant_isolation.py`

**Coverage expansion required**

Convert `docs/qa/route-auth-tenant-inventory.md` into executable negative tests for every high-risk route marked:

- `auth signal: public/unknown`
- `tenant note: unknown`
- file/photo/PDF/export/certificate/submission/supply-chain write routes

---

### P0-3. Supply-Chain Traceability / Public QR / Sealed Snapshot

**Invariants**

- Public trace uses opaque immutable `public_trace_id`, never tenant-local `batch_code` as lookup key.
- Public trace returns 200 only for completed/sealed/public-enabled batches with sealed snapshot and integrity hash.
- Invalid/malformed/injection IDs fail closed.
- Public trace never leaks internal IDs/private metadata.
- Sealed batches are immutable.

**Automated evidence**

- `backend/tests/test_supply_chain_sealing.py`
- `backend/tests/test_supply_chain_batches.py`
- `backend/tests/test_supply_chain_suppliers.py`
- `backend/tests/test_supply_chain_materials.py`
- `backend/tests/test_supply_chain_processes.py`
- `backend/tests/test_supply_chain_supplier_eligibility_routes.py`
- `scripts/qa/seed-public-trace-fixture.py`
- `frontend/aminra-web/e2e/10-supply-chain.spec.ts`
- `frontend/aminra-web/e2e/33-batch1-workflow-integrity.spec.ts`
- `frontend/aminra-web/e2e/40-supply-chain-create-contracts.spec.ts`
- `frontend/aminra-web/e2e/38-demo-spine-keycloak.spec.ts`

**Runtime smoke**

- Valid deterministic trace fixture returns backend API 200.
- Public proxy path returns 200.
- Invalid and injection IDs return 404.
- Browser page hydrates success and not-found states.
- Response has no `tenant_id`, `provider_id`, `source_certificate_id`, `changed_by` markers.

---

### P0-4. Supplier/NCC Eligibility / CB Authority

**Invariants**

- Business-uploaded supplier document cannot create operational eligibility.
- Provider/CB can mutate eligibility only if backed by source certificate/licence authority.
- Provider B cannot modify Provider A eligibility.
- Expired/revoked/suspended certs fail closed.
- Material/batch creation rejects ineligible suppliers.

**Automated evidence**

- `backend/tests/test_supplier_eligibility_service.py`
- `backend/tests/test_supply_chain_supplier_eligibility_routes.py`
- `backend/tests/test_migrations_supplier_eligibility.py`
- `backend/tests/test_supply_chain_materials.py`
- `backend/tests/test_supply_chain_batches.py`
- `frontend/aminra-web/e2e/40-supply-chain-create-contracts.spec.ts`

---

### P0-5. Submission Lifecycle / Certification Lifecycle

**Invariants**

- Submission transition matrix is enforced by role and state.
- Approved/finalized submissions lock documents against upload/replace/delete.
- Revision-required resubmit requires actual corrective change.
- AI compliance score is not overwritten by approval/finalization.
- Cert numbers are unique under concurrency.
- Revoke/suspend is provider-scoped and cannot cross-provider mutate.
- Public verify exposes safe fields and correct status.

**Automated evidence**

- `backend/tests/test_submission_revisions_unit.py`
- `backend/tests/test_submission_revisions_integration.py`
- `backend/tests/test_submission_sla_unit.py`
- `backend/tests/test_submission_sla_integration.py`
- `backend/tests/uat/test_uat_a_cert_lifecycle.py`
- `backend/tests/uat/test_uat_d_cert_verify_recall.py`
- `backend/tests/test_cert_lifecycle_unit.py`
- `backend/tests/test_cert_lifecycle_integration.py`
- `backend/tests/test_certificate_pdf_unit.py`
- `backend/tests/test_certificate_pdf_integration.py`
- `backend/tests/test_certificate_pdf_integrity_smoke.py`
- `backend/tests/test_public_verify_blockchain.py`
- `frontend/aminra-web/e2e/14-cuj-cert-lifecycle.spec.ts`
- `frontend/aminra-web/e2e/35-batch5-state-scoring.spec.ts`

**Known gap tests to add if absent**

- `backend/tests/test_submission_state_machine.py`
- `backend/tests/test_submission_document_lock.py`
- `backend/tests/test_certificate_lifecycle_scope.py`
- `backend/tests/test_certificate_number_concurrency.py`

These are P0 gaps until proven by existing tests or implemented.

---

### P0-6. Admin / User / Business Member / Provider Auditor CRUD

**Invariants**

- Admin CRUD uses platform-admin realm role.
- Profile update and password reset are separate paths.
- Business member/provider auditor invite writes canonical AMINRA `users.id`, not Keycloak `sub`.
- Delete/disable removes login capability and leaves no Keycloak orphan.
- Lower roles cannot access admin/provider/business-owner actions.

**Automated evidence**

- `backend/tests/test_admin_user_password_reset.py`
- `backend/tests/test_admin_crud_unit.py`
- `backend/tests/test_auth_invite_canonical_invited_by.py`
- `backend/tests/test_company_logo_empty_state.py`
- `backend/tests/test_kc_sub_fk_smoke.py`
- `frontend/aminra-web/e2e/05-admin-flow.spec.ts`
- `frontend/aminra-web/e2e/20-admin-unified-auth.spec.ts`
- `frontend/aminra-web/e2e/21-admin-pages-token-pattern.spec.ts`
- `frontend/aminra-web/e2e/30-admin-user-edit-ux.spec.ts`

---

### P1-7. PDF / Document Rendering / Versioning / Official Artifacts

**Invariants**

- Official-looking artifacts require auth and correct tenant/role/state.
- Render/export endpoints cannot be unauthenticated leak paths.
- Template/file upload is path-safe.
- PDF output handles sparse data, hostile text, Unicode, long text, and deterministic artifact expectations where needed.
- Versioning state machine, retention, audit, and cross-tenant chain constraints hold.

**Automated evidence**

- `backend/tests/integration/test_pdf_full_pipeline.py`
- `backend/tests/test_schema_aware_data_unit.py`
- `backend/tests/test_pdf_filter_pipeline_unit.py`
- `backend/tests/test_pdf_data_aggregator_unit.py`
- `backend/tests/visual/test_pdf_baselines.py` when `RUN_VISUAL=1`
- `backend/tests/test_document_versioning_unit.py`
- `backend/tests/test_document_versioning_integration.py`
- `backend/tests/test_document_versioning_sec.py`
- `backend/tests/test_document_versioning_func.py`
- `backend/tests/test_document_versioning_regression.py`
- `frontend/aminra-web/e2e/27-template-content-integrity.spec.ts`
- `frontend/aminra-web/e2e/28-admin-template-view.spec.ts`
- `frontend/aminra-web/e2e/31-revision-panel-visibility.spec.ts`
- `frontend/aminra-web/e2e/34-batch4-file-llm-safety.spec.ts`

---

### P1-8. Async Jobs / ARQ / Compliance Workers / Observability

**Invariants**

- ARQ worker has the same env/secret access needed by backend.
- Worker initializes DB outside FastAPI lifespan.
- Certificate expiry/SLA jobs are idempotent, tenant-safe, and produce structured logs/metrics.
- Job failure is visible and does not print secrets.

**Automated evidence**

- `backend/tests/test_jobs_unit.py`
- `backend/tests/test_jobs_integration.py`
- `backend/tests/test_anchor_job_unit.py`
- `backend/tests/test_cert_lifecycle_unit.py`
- `backend/tests/test_submission_sla_unit.py`
- `backend/tests/test_submission_sla_integration.py`
- high-signal Docker log scan after worker dry-runs

---

### P1-9. Data Rights / Audit / Rate Limit / Upload Security

**Invariants**

- Data export/deletion is tenant-scoped and audit logged.
- Audit logs are append-only for sensitive actions.
- Upload validation rejects dangerous names, extensions, oversized files, path traversal, and wrong MIME.
- Rate limits protect upload/render/data export paths.

**Automated evidence**

- `backend/tests/test_data_export_unit.py`
- `backend/tests/test_data_export_integration.py`
- `backend/tests/test_data_deletion_unit.py`
- `backend/tests/test_data_deletion_integration.py`
- `backend/tests/test_audit_log_unit.py`
- `backend/tests/test_audit_log_integration.py`
- `backend/tests/test_audit_log_coverage.py`
- `backend/tests/test_upload_validation.py`
- `backend/tests/test_config_tunables.py`

**Known backlog**

- Route-bucket rate-limit load test for upload/pdf_render/data_export.
- Append-only audit tamper resistance periodic check.

---

### P1-10. Frontend Critical Contracts / Build / Browser / Accessibility

**Invariants**

- Frontend does not show false success after non-2xx writes.
- FastAPI error shapes are rendered safely.
- Build/lint pass.
- Critical role pages render.
- Mobile/WebKit/Safari/demo spine works.
- Accessibility has no critical violations; serious warnings tracked.

**Automated evidence**

- `cd frontend/aminra-web && npm test`
- `cd frontend/aminra-web && npm run lint`
- `cd frontend/aminra-web && npm run build`
- focused Playwright critical set:
  - `e2e/38-demo-spine-keycloak.spec.ts`
  - `e2e/40-supply-chain-create-contracts.spec.ts`
  - `e2e/accessibility.spec.ts`
  - `e2e/19-mobile-responsive-audit.spec.ts`
- full Playwright matrix when `RUN_FULL_E2E=1`.

---

### P1-11. Load / Performance / Chaos / Deploy Safety

**Invariants**

- Public trace repeated and cold-cache load meets accepted sandbox SLO.
- Redis/Qdrant/Keycloak outage behavior is known and recovers.
- Backend recreate during traffic is classified as downtime risk.
- Registry deploy script fails closed unless explicit maintenance window is approved.

**Automated evidence**

- Public trace performance probe when `RUN_LOAD=1`.
- Chaos drills when `RUN_CHAOS=1`.
- `scripts/deploy-from-registry.sh` safety gate dry-runs.

---

## 5. Required final report structure

Every execution must write:

1. Environment baseline.
2. Git status/diff boundary.
3. Suite result table by domain.
4. P0 defects.
5. P1 defects.
6. Deferred gates — SMTP/verifyEmail at minimum.
7. Blocked gates — missing credentials/approval/environment.
8. Evidence index.
9. Cleanup status for QA fixtures.
10. Verdict lanes:
    - sandbox_demo
    - supervised_pilot
    - customer_onboarding
    - production_go

---

## 6. Success criteria before customers use the system

### Controlled sandbox demo

Required:

- Runtime smoke PASS.
- Role-boundary/demo spine PASS.
- Public trace valid/invalid PASS.
- No P0 tenant/auth/public leak FAIL.
- Known limitations scripted.

### Supervised pilot

Required:

- All sandbox demo gates.
- Admin/user/member/auditor CRUD PASS.
- Submission/cert lifecycle P0 gates PASS.
- Supply-chain CB authority PASS.
- ARQ compliance jobs PASS.
- Maintenance-window deploy policy accepted.
- Secrets available from canonical source, not ad-hoc chat.

### Customer onboarding / production

Required:

- All supervised pilot gates.
- SMTP/verifyEmail/password reset live-send PASS.
- Secrets in Vault/secret manager.
- No dirty release tree.
- Rollback plan.
- Load/resilience accepted.
- Legal/privacy/customer data policy approved.

Because SMTP is deferred, customer onboarding and production cannot be PASS from this plan yet.
