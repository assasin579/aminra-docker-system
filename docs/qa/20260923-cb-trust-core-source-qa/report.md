# AMINRA CB Trust Core — Source QA Report

Date: 2026-09-23
Branch: feat/cb-trust-core-rbac-decisions
Scope: Week 1-3 source implementation only — RBAC v0, certification decision independence, conflict-of-interest controls, complaints/appeals MVP, minimal UI contract pages.

## Verdict

SOURCE / BUILD PASS.
RUNTIME NOT RUN.
DEPLOY NOT RUN.
COMMIT NOT RUN.

This is not a production/customer-pilot GO. The implementation is source-verified and independently security-reviewed, but live migrations, container rebuild/recreate, credentialed browser UAT, and runtime smoke were intentionally not performed because they require separate approval.

## Implemented

### Week 1 — RBAC + certification decision independence
- Added lightweight centralized policy service and dependency helper.
- Added CB trust route inventory script and contract tests.
- Added certification decision migration/service/router.
- Added certificate issuance gate requiring approved certification decision(s).
- Enforced auditor/linked audit-visit auditor cannot approve/reject own case.
- Enforced provider/business object scoping for create/read/finalize.
- Added rejected-decision supersession semantics: latest non-cancelled decision drives issuance; rejected can be superseded by later approved decision.
- Added race-safe finalization update with `status='pending_review'` condition.

### Week 2 — Conflict of interest
- Added conflict declaration/review/override schema/service/router.
- Unresolved conflicts block audit assignment and certification decision finalization.
- Override requires reason and provider authority.
- Added minimal `/conflicts` frontend source-contract page.

### Week 3 — Complaints/appeals
- Added complaints/appeals migration/service/router.
- Authenticated-only MVP; no anonymous public intake.
- Appeal requires original decision and enforces handler independence.
- Original decision maker and linked audit auditor cannot handle appeal.
- Assignment validates provider-staff owner in the same provider boundary.
- Complaint/appeal submission and certificate IDs are validated for existence/scope.
- Added minimal `/complaints` frontend source-contract page.

## Final verification gates

Backend focused/regression gate:

```bash
docker cp backend/. aminra-docker-system-aminra-backend-1:/app/
docker compose exec -T aminra-backend bash -lc 'cd /app && pytest -q tests/test_rbac_policy_engine.py tests/test_cb_trust_route_inventory.py tests/test_certification_decision_migration_contract.py tests/test_certification_decision_independence.py tests/test_certificate_decision_gate.py tests/test_certification_decision_router.py tests/test_conflict_interest_migration_contract.py tests/test_conflict_interest_service.py tests/test_conflict_interest_router.py tests/test_audit_assignment_conflict_block.py tests/test_complaints_appeals_migration_contract.py tests/test_complaints_appeals_service.py tests/test_complaints_appeals_router.py tests/test_certificate_pdf_integration.py tests/test_certificate_lifecycle_scope.py tests/test_submission_state_machine.py tests/uat/test_uat_b_audit_ncr.py'
```

Result: `88 passed, 44 skipped`.

Static/backend guardrails:

```bash
git diff --check
python3 backend/scripts/kc_sub_fk_guard.py
```

Result: PASS. `Keycloak sub FK guard passed`.

Frontend source contracts/lint/build:

```bash
cd frontend/aminra-web
npm test -- --run __tests__/conflict-interest-ui-contract.test.tsx __tests__/complaints-appeals-ui-contract.test.tsx
npm run lint
npm run build
```

Result:
- Vitest: `2 passed`.
- ESLint: PASS with `--max-warnings=0`.
- Next build: PASS.
- Non-blocking existing warnings: Sentry Next.js deprecation warnings for `withSentryConfig` import and `disableLogger`.

Independent review:
- Final security approval: APPROVED.
- Previous important issues fixed before approval:
  - cross-business appeal creation gap;
  - arbitrary complaint/appeal owner assignment;
  - race-prone certification finalization;
  - invalid reviewer assignment;
  - non-appeal complaint arbitrary certificate/submission references;
  - reviewer equals linked audit-visit auditor.

## Key files

Backend created/changed:
- `backend/auth/policy_service.py`
- `backend/auth/policy_dependency.py`
- `backend/scripts/cb_trust_route_inventory.py`
- `backend/alembic/versions/047_cert_decisions.py`
- `backend/alembic/versions/048_conflicts_interest.py`
- `backend/alembic/versions/050_complaints_appeals.py`
- `backend/auth/certification_decision_router.py`
- `backend/auth/conflict_router.py`
- `backend/auth/complaints_router.py`
- `backend/services/certification_decisions.py`
- `backend/services/conflict_interest.py`
- `backend/services/complaints_appeals.py`
- `backend/auth/certificate_router.py`
- `backend/auth/audit_router.py`
- `backend/app.py`

Frontend created:
- `frontend/aminra-web/app/conflicts/page.tsx`
- `frontend/aminra-web/app/complaints/page.tsx`
- `frontend/aminra-web/__tests__/conflict-interest-ui-contract.test.tsx`
- `frontend/aminra-web/__tests__/complaints-appeals-ui-contract.test.tsx`

Tests added/updated:
- `backend/tests/test_rbac_policy_engine.py`
- `backend/tests/test_cb_trust_route_inventory.py`
- `backend/tests/test_certification_decision_migration_contract.py`
- `backend/tests/test_certification_decision_independence.py`
- `backend/tests/test_certification_decision_router.py`
- `backend/tests/test_certificate_decision_gate.py`
- `backend/tests/test_conflict_interest_migration_contract.py`
- `backend/tests/test_conflict_interest_service.py`
- `backend/tests/test_conflict_interest_router.py`
- `backend/tests/test_audit_assignment_conflict_block.py`
- `backend/tests/test_complaints_appeals_migration_contract.py`
- `backend/tests/test_complaints_appeals_service.py`
- `backend/tests/test_complaints_appeals_router.py`

## Known gaps / next required gates

Before runtime/demo claim:
1. Apply Alembic migrations only on approved local/sandbox DB with backup.
2. Rebuild/recreate backend/frontend only after approval.
3. Run health checks and credentialed browser UAT for CB/provider/business/auditor roles.
4. Verify conflict/decision/appeal flows against real tokens and real DB rows.
5. Decide whether minimal UI pages should become fully wired API clients or remain source-contract placeholders for now.

## Safety notes

- No commit, push, deploy, restart, or live migration was performed.
- Tests were run in the existing backend container after syncing source with `docker cp`; this verifies source behavior in the container test environment, not the currently deployed runtime image.
- Working tree contains many new/untracked CB Trust files; if preparing a commit, stage intended files explicitly before commit so CI/deploy does not miss untracked feature files.
