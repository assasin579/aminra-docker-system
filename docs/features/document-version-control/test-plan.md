# Feature #24 — Test Plan (Stage 4)

**Methodology**: ≥50 cases per category × 6 categories = ≥300 tests. TDD-friendly — implementation must satisfy these. Each test gets a stable ID prefix used in commit messages and the test report.

**Categories**: UNIT (pure logic), INT (router→service→DB), SMOKE (regression of existing endpoints), FUNC (business workflow E2E), UAT (Gherkin per persona), SEC (STRIDE-driven).

**File mapping (will be created in Stage 5)**:
- `backend/tests/test_document_versioning_unit.py` — UNIT-* + part of FUNC
- `backend/tests/test_document_versioning_integration.py` — INT-* + SEC-* (DB-dependent)
- `backend/tests/test_document_versioning_regression.py` — SMOKE-*
- `backend/tests/bdd/document_versioning.feature` + `test_document_versioning_bdd.py` — UAT-*
- `frontend/aminra-web/__tests__/featureFlags.test.tsx` — frontend UNIT subset
- `frontend/aminra-web/e2e/40-doc-version-control.spec.ts` — UAT-* Playwright slice + SMOKE flag-toggling

---

## 1. UNIT (50) — pure logic, no DB, no HTTP

### State machine (15)
- UNIT-01 `transition_allowed(draft, pending_approval, can_edit)` → True
- UNIT-02 `transition_allowed(draft, approved, can_approve)` → False (skip-approval forbidden)
- UNIT-03 `transition_allowed(pending_approval, approved, can_approve)` → True
- UNIT-04 `transition_allowed(pending_approval, draft, can_approve)` → True (rejection)
- UNIT-05 `transition_allowed(pending_approval, draft, can_edit_only)` → True (own submission rollback)
- UNIT-06 `transition_allowed(approved, draft, *)` → False
- UNIT-07 `transition_allowed(approved, pending_approval, *)` → False (must use supersede)
- UNIT-08 `transition_allowed(obsolete, *, *)` → False (terminal state)
- UNIT-09 `transition_allowed(approved, obsolete, supersede_actor)` → True
- UNIT-10 `transition_allowed(draft, obsolete, *)` → False
- UNIT-11 `transition_reason_required(pending_approval → draft)` → True (rejection needs reason)
- UNIT-12 `transition_reason_required(draft → pending_approval)` → False
- UNIT-13 `transition_reason_required(pending_approval → approved)` → False
- UNIT-14 `state_machine_emits_audit_event(*, approved)` → "document.approved"
- UNIT-15 `state_machine_emits_audit_event(pending_approval, draft)` → "document.approval_rejected"

### Permission helpers (8)
- UNIT-16 `get_user_permissions({is_owner: true, ihc_role: null}).can_approve_documents` → True
- UNIT-17 `get_user_permissions({is_owner: false, ihc_role: 'chair'}).can_approve_documents` → True
- UNIT-18 `get_user_permissions({is_owner: false, ihc_role: null}).can_approve_documents` → False
- UNIT-19 `get_user_permissions({is_owner: false, permissions: {can_approve_documents: true}}).can_approve_documents` → True (explicit override)
- UNIT-20 `get_user_permissions({})` no crash on missing fields → returns dict with all False
- UNIT-21 `_explicit_permissions(None)` → empty dict
- UNIT-22 `_explicit_permissions({"permissions": "{\"x\":1}"})` → parses JSON string
- UNIT-23 `_explicit_permissions({"permissions": {"x":1}})` → handles dict directly

### Retention calculation (5)
- UNIT-24 `compute_retention_expires(approved_at=2026-01-15, effective_date=None, days=1825)` → 2031-01-15 (5y from approved_at)
- UNIT-25 `compute_retention_expires(approved_at=2026-01-15, effective_date=2026-01-20, days=1825)` → 2031-01-20 (5y from effective_date)
- UNIT-26 `compute_retention_expires(approved_at=*, effective_date=*, days=1824)` raises ValueError (floor)
- UNIT-27 `compute_retention_expires(approved_at=*, effective_date=*, days=3650)` → 10y from base date
- UNIT-28 `compute_retention_expires(approved_at=None, effective_date=2026-01-20, days=1825)` raises (need at least one base)

### Version chain helpers (8)
- UNIT-29 `chain_depth(parent=None)` → 0
- UNIT-30 `chain_depth(parent=parent_with_depth_1)` → 1
- UNIT-31 `next_version_number(parent_with_version_3)` → 4
- UNIT-32 `next_version_number(parent=None)` → 1
- UNIT-33 `validate_chain_links(child={parent: A, supersede: B})` raises (parent + supersede mutually exclusive on insert)
- UNIT-34 `chain_is_obsolete(doc with superseded_by_id set)` → True
- UNIT-35 `chain_root(doc whose parent points to root)` → root id
- UNIT-36 `chain_root(doc with no parent)` → self id

### Approval payload validation (7)
- UNIT-37 `ApprovalRequest(effective_date='2026-01-15')` → valid
- UNIT-38 `ApprovalRequest(effective_date='not-a-date')` → ValidationError
- UNIT-39 `ApprovalRequest(effective_date='2024-01-15')` (past) → valid (backdating allowed) + warning flag
- UNIT-40 `ApprovalRequest(retention_period_days=100)` → ValidationError (floor 1825)
- UNIT-41 `ApprovalRequest(retention_period_days=99999)` → valid (no upper limit)
- UNIT-42 `ApprovalRequest()` empty body → defaults applied (effective_date=today, next_review=+1y, retention=1825)
- UNIT-43 `RejectionRequest(reason='')` → ValidationError (reason required, ≤500)

### Frontend hook (7)
- UNIT-44 `useFeature("document_versioning_v1")` returns false on first render before fetch
- UNIT-45 `useFeature` returns true after fetch resolves with flag enabled
- UNIT-46 `FeatureFlagProvider` does not crash when no token
- UNIT-47 `FeatureFlagProvider` SSR-safe (no `window` access in server render)
- UNIT-48 Approval modal closed by default; opens on button click
- UNIT-49 Approval modal default values: effective_date=today, next_review=+1y, retention=1825
- UNIT-50 Approval modal disables submit while in flight (no double-click)

---

## 2. INT (50) — router → service → DB roundtrip

Requires: live backend + migration 017 applied + 2 seeded tenants (A, B) + users per persona.

### Endpoint happy paths (12)
- INT-01 `POST /api/documents/{id}/submit-for-approval` (owner) → 200, `approval_status='pending_approval'`
- INT-02 `POST /api/documents/{id}/submit-for-approval` (member can_edit) → 200
- INT-03 `POST /api/documents/{id}/approve` (owner approver) → 200, fields populated
- INT-04 `POST /api/documents/{id}/approve` body with custom dates → values stored
- INT-05 `POST /api/documents/{id}/approve` empty body → defaults (today, +1y, 1825d)
- INT-06 `POST /api/documents/{id}/reject` with reason → 200, returns to draft
- INT-07 `POST /api/documents/{id}/supersede` with new doc → both rows updated atomically
- INT-08 `GET /api/documents/{id}/versions` returns chain in order
- INT-09 `GET /api/documents/{id}/approval-status` returns full approval block
- INT-10 IHC member (`ihc_role='chair'`) can approve → 200
- INT-11 Approval triggers DB-level retention_expires_at compute (not just app-layer)
- INT-12 Supersede triggers DB-level approval_status='obsolete' on old row

### Error states (12)
- INT-13 Submit-for-approval on already pending → 409
- INT-14 Submit-for-approval on already approved → 409
- INT-15 Approve from draft (skip pending) → 409
- INT-16 Approve by non-approver (member without permission) → 403
- INT-17 Reject without reason → 422
- INT-18 Reject with reason >500 chars → 422
- INT-19 Approve with retention < 1825 → 422
- INT-20 Supersede with already-obsolete doc → 409
- INT-21 Supersede with same doc as new (self-link) → 422
- INT-22 Approve a non-existent doc → 404
- INT-23 Versions of non-existent doc → 404
- INT-24 Endpoint with feature flag OFF → 404 (all 6 new endpoints)

### Tenant isolation (10)
- INT-25 Tenant A user cannot submit-for-approval tenant B's doc → 404 (not 403, to avoid existence-leak)
- INT-26 Tenant A user cannot approve tenant B's doc → 404
- INT-27 Tenant A user cannot reject tenant B's doc → 404
- INT-28 Tenant A user cannot supersede with tenant B's doc → DB trigger raises 23514
- INT-29 Tenant A user GET /versions of tenant B doc → 404
- INT-30 Tenant A's supersede chain doesn't expose tenant B's parent → empty/404
- INT-31 Provider auditor reading their assigned submission's doc CAN see approval state
- INT-32 Provider auditor reading non-assigned doc → 403
- INT-33 Admin reading any tenant's approval state for audit → 200 read-only
- INT-34 Admin cannot mutate approval state → 403

### DB trigger behavior (8)
- INT-35 Trigger blocks INSERT with cross-tenant version_parent_id → 23514 SQLSTATE
- INT-36 Trigger blocks UPDATE setting cross-tenant superseded_by_id → 23514
- INT-37 Trigger auto-sets retention_expires_at on first approval transition
- INT-38 Trigger does NOT recompute retention_expires_at on idempotent UPDATE (e.g., changing notes only)
- INT-39 Trigger auto-flips approval_status to 'obsolete' when superseded_by_id is set
- INT-40 Delete-block trigger raises 23503 when doc has children
- INT-41 Delete trigger allows delete when doc has no children
- INT-42 Trigger does NOT block delete when only `superseded_by` link exists (block_delete_with_children only checks parent linkage downward)

### Audit log + migration (8)
- INT-43 Audit log row inserted in same TX as approval (fail simulation: TX rollback also rolls audit)
- INT-44 Audit log row references tenant_id correctly
- INT-45 Audit log captures rejection reason in metadata
- INT-46 Audit log captures effective_date + retention in metadata at approval
- INT-47 Migration 017 apply on fresh DB → 10 columns added, 2 triggers, 5 indexes
- INT-48 Migration 017 backfill: legacy 'approved' rows mapped correctly
- INT-49 Migration 017 downgrade reverses: columns dropped, triggers dropped
- INT-50 Re-apply migration 017 (post-downgrade) → idempotent (same state)

---

## 3. SMOKE (50) — regression of existing endpoints

Run with feature flag both OFF and ON. Most assertions: response shape unchanged when OFF, additive fields when ON.

### Existing endpoint × flag-OFF baseline (12)
- SMOKE-01 `GET /api/documents` flag-OFF → byte-identical to pre-Phase-1 baseline (snapshot fixture)
- SMOKE-02 `GET /api/documents/{id}` flag-OFF → no new fields in response
- SMOKE-03 `GET /api/documents/revisions/{doc_type_id}` flag-OFF → unchanged
- SMOKE-04 `POST /api/documents/upload` flag-OFF → upload succeeds, response unchanged
- SMOKE-05 `POST /api/documents/{id}/promote` flag-OFF → legacy behavior (status=approved, no approval_status touched)
- SMOKE-06 `GET /api/documents/{id}/preview` flag-OFF → preview returns same content
- SMOKE-07 `GET /api/documents/{id}/file` flag-OFF → file download unchanged
- SMOKE-08 `POST /api/documents/{id}/evaluate` flag-OFF → LLM evaluation unchanged
- SMOKE-09 `DELETE /api/documents/{id}` flag-OFF → still allowed even with chain children (legacy)
- SMOKE-10 `GET /api/dashboard/stats` flag-OFF → counts unchanged
- SMOKE-11 `POST /api/submissions/submit` flag-OFF → submit with mixed-status docs allowed
- SMOKE-12 `GET /api/users/me/export-data` flag-OFF → GDPR export omits new fields

### Existing endpoint × flag-ON additions (12)
- SMOKE-13 `GET /api/documents` flag-ON → response items include `approval_status`, `version_number`
- SMOKE-14 `GET /api/documents/{id}` flag-ON → full approval block included
- SMOKE-15 `GET /api/documents/revisions/{doc_type_id}` flag-ON → version chain visible
- SMOKE-16 `POST /api/documents/upload` flag-ON → new doc has `approval_status='draft'`, `version_number=1`
- SMOKE-17 `POST /api/documents/{id}/promote` flag-ON (uploaded) → both status='approved' AND approval_status='approved' set
- SMOKE-18 `POST /api/documents/{id}/promote` flag-ON (rejected) → 409 (must re-submit)
- SMOKE-19 `POST /api/documents/{id}/promote` flag-ON (already approved) → no-op
- SMOKE-20 `POST /api/documents/{id}/promote` flag-ON (pending_approval) → 409
- SMOKE-21 `POST /api/documents/{id}/evaluate` flag-ON → unchanged (no interaction with approval)
- SMOKE-22 `DELETE /api/documents/{id}` flag-ON (no children) → 200
- SMOKE-23 `DELETE /api/documents/{id}` flag-ON (with children) → 409 with "supersede first" hint
- SMOKE-24 `GET /api/users/me/export-data` flag-ON → GDPR export includes new fields per tenant

### Frontend pages (8)
- SMOKE-25 `/documents` list renders without errors flag-OFF
- SMOKE-26 `/documents` list shows new badge column flag-ON
- SMOKE-27 `/documents/{id}` detail renders without errors flag-OFF
- SMOKE-28 `/documents/{id}` detail shows approval block flag-ON
- SMOKE-29 `/dashboard/business` renders flag-OFF
- SMOKE-30 `/dashboard/business` shows readiness based on approval state flag-ON
- SMOKE-31 `/submissions` renders flag-OFF + ON
- SMOKE-32 Sidebar nav links unchanged

### Service health (5)
- SMOKE-33 `/health` returns 200 + service name
- SMOKE-34 `/metrics` returns Prometheus format
- SMOKE-35 `/metrics` includes `aminra_http_requests_total{route="/api/documents/{id}/submit-for-approval"}` counter
- SMOKE-36 X-Request-ID propagated on new endpoints
- SMOKE-37 Structured JSON logs include request_id, tenant_id, user_id

### Cross-endpoint workflows (8)
- SMOKE-38 Upload → submit → approve → effective: full chain results in valid approved doc
- SMOKE-39 Upload → /promote (legacy) flag-OFF: status='approved' + approval_status NULL
- SMOKE-40 Upload → /promote (legacy) flag-ON: both columns aligned
- SMOKE-41 Submission with mixed approval statuses: works in v1, flag for SME
- SMOKE-42 GDPR export of business with 5 docs in mixed states: shape correct
- SMOKE-43 Audit log query for "document.approved" event in last hour: returns expected
- SMOKE-44 Notification fired on approval (existing notification_router unchanged)
- SMOKE-45 Submission update path (resubmit) does NOT alter approval_status

### Negative regression (5)
- SMOKE-46 Existing pytest suite for `test_data_export_unit.py` still passes
- SMOKE-47 Existing pytest suite for `test_audit_log_unit.py` still passes
- SMOKE-48 Existing pytest suite for `test_submission_revisions_unit.py` still passes
- SMOKE-49 Coverage on `auth/document_router.py` not lower than baseline
- SMOKE-50 Coverage on `services/data_export.py` not lower than baseline

---

## 4. FUNC (50) — business workflow end-to-end

### Approval flow per persona (30 = 5×6)
For each of 5 personas (BusinessOwner, BusinessMemberApprover, BusinessMemberNonApprover, IHCMember, ProviderAuditor), run scenarios:

- FUNC-01..05: P1 → upload → submit → expect pending
- FUNC-06..10: P2 → can approve own tenant doc → expect approved
- FUNC-11..15: P3 → cannot approve (member without perm) → 403
- FUNC-16..20: P4 → IHC member can approve via ihc_role auto-perm
- FUNC-21..25: P5 → provider auditor cannot approve (cross-tenant) → 403/404
- FUNC-26..30: P6 → admin cannot mutate, can read-only audit trail

### /promote decision matrix (10)
Cells from threat-model §C.1:
- FUNC-31 /promote on uploaded, flag OFF → status=approved (legacy)
- FUNC-32 /promote on uploaded, flag ON → status=approved + approval_status=approved + approver_id=actor + audit
- FUNC-33 /promote on approved, flag OFF → idempotent
- FUNC-34 /promote on approved, flag ON → idempotent
- FUNC-35 /promote on rejected, flag OFF → status=approved (legacy quirk)
- FUNC-36 /promote on rejected, flag ON → 409
- FUNC-37 /promote on reviewing, flag OFF → status=approved (legacy)
- FUNC-38 /promote on reviewing, flag ON → 409
- FUNC-39 /promote on pending_approval, flag ON → 409
- FUNC-40 /promote on obsolete, flag ON → 409

### Supersede + version chain (5)
- FUNC-41 Supersede creates obsolete + new version with chain link
- FUNC-42 Supersede chain depth 3: A→B→C, /versions returns 3 in order
- FUNC-43 Supersede with provider's review pending: provider notified
- FUNC-44 Supersede preserves audit trail of all 3 versions
- FUNC-45 Supersede when child already exists: 409

### Audit trail completeness (5)
- FUNC-46 Each approval transition emits exactly 1 audit row
- FUNC-47 Rejection emits 1 row with reason
- FUNC-48 Supersede emits row on old doc only (not new)
- FUNC-49 Audit log query by entity_id returns full doc history (chronological)
- FUNC-50 Audit log query by user_id returns approver's actions across docs

---

## 5. UAT (50) — Gherkin per persona

`backend/tests/bdd/document_versioning.feature` — Gherkin scenarios. Step impl in `test_document_versioning_bdd.py`.

### Business owner (10)
- UAT-01 Upload then submit for approval: see pending status
- UAT-02 Approve own doc: badge changes to approved
- UAT-03 Reject with reason: doc returns to draft, reason visible to submitter
- UAT-04 Supersede with new uploaded version: old marked obsolete
- UAT-05 View version history: see all 3 versions in chain
- UAT-06 Set custom effective_date in past: warning toast shown but accepted
- UAT-07 Try to set retention 100 days: error toast "minimum 5 years"
- UAT-08 Delete doc with no children: success
- UAT-09 Delete doc with children: error "supersede first"
- UAT-10 Promote (legacy button): now creates approval audit entry

### Business member with approve permission (8)
- UAT-11 Submit own draft for approval
- UAT-12 Approve another member's pending doc
- UAT-13 Reject another member's pending doc
- UAT-14 Cannot supersede (owner-only)
- UAT-15 Read approval history of any doc in tenant
- UAT-16 Toast on approval action confirms persistence
- UAT-17 Notification fired to submitter on approval/rejection
- UAT-18 Sidebar shows total pending docs awaiting their approval

### Business member without approve permission (8)
- UAT-19 Can submit own draft
- UAT-20 Cannot see approve/reject buttons in UI
- UAT-21 Direct API approve attempt → 403 with friendly error
- UAT-22 Read approval history (read-only)
- UAT-23 Cannot supersede or set effective dates
- UAT-24 Toast notification on doc approval by another user
- UAT-25 Cannot rollback own submission once approved
- UAT-26 Owner toggling permission ON: UI updates within session

### IHC member (8)
- UAT-27 IHC chair approves doc with effective_date today
- UAT-28 IHC chair approves with custom retention 10 years
- UAT-29 IHC secretary cannot supersede (only owner)
- UAT-30 IHC member views audit trail filtered by IHC actions
- UAT-31 IHC role removed mid-session: approval permission revoked
- UAT-32 Sidebar shows IHC role badge
- UAT-33 IHC bulk-approve list (deferred to Phase 2; this UAT skips)
- UAT-34 IHC chair rejection includes "shariah concern" reason category (free text)

### Provider/auditor read-only (8)
- UAT-35 Auditor sees approval state on submission docs
- UAT-36 Auditor cannot approve/reject from review screen
- UAT-37 Auditor sees full version history of submitted docs
- UAT-38 Auditor of tenant A cannot read tenant B's docs
- UAT-39 Auditor sees retention expiry → flagged if past
- UAT-40 Auditor exports submission with approval evidence
- UAT-41 Auditor's session shows all approval events in audit log
- UAT-42 Auditor cannot supersede (cross-tenant action)

### Admin (8)
- UAT-43 Admin reads approval audit logs across tenants
- UAT-44 Admin cannot mutate approval (403 on POST/PUT)
- UAT-45 Admin sees retention expiry overdue list
- UAT-46 Admin can read version chains for forensics
- UAT-47 Admin GDPR export request for any tenant: includes approval state
- UAT-48 Admin sees feature flag status for `document_versioning_v1`
- UAT-49 Admin can override flag per tenant (existing feature-flag admin)
- UAT-50 Admin sees frequency of /promote vs /approve calls in metrics

---

## 6. SEC (50) — STRIDE-driven from threat model

### R1 Approver elevation (5)
- SEC-01 Member without can_approve_documents calls /approve → 403
- SEC-02 Member with permission revoked mid-session: stale token rejected on next /approve
- SEC-03 Admin attempts business-tenant /approve → 403 (admin doesn't have tenant_id)
- SEC-04 JWT with `is_owner=true` claim but DB shows `is_owner=false` → server uses DB, returns 403
- SEC-05 Expired JWT on /approve → 401

### R2 Cross-tenant version-chain leak (5)
- SEC-06 Tenant A POST supersede pointing to tenant B doc → 23514 trigger error → 422 with safe message
- SEC-07 Direct DB INSERT with cross-tenant version_parent_id → trigger blocks
- SEC-08 /versions of doc in tenant A as tenant B user → 404 (no leak)
- SEC-09 /versions recursion limited to depth 10 → 11th level truncated with warning header
- SEC-10 Self-referential parent_id (id == parent_id) rejected by app layer → 422

### R3 Status-machine bypass (10)
Mirrors FUNC-31..40 but framed as security:
- SEC-11..20 = same cells but assert: no audit drift, no incomplete state, no privilege escalation via /promote

### R4 Retention tampering (5)
- SEC-21 POST /approve with retention_period_days=1 → 422
- SEC-22 PUT-equivalent attempt to mutate retention after approval → no such endpoint exposed
- SEC-23 Direct DB UPDATE retention_period_days → app-layer query no-op (retention_expires_at not recomputed; audit divergence detectable in next audit run)
- SEC-24 Approve then re-approve flow: retention not reset to fresh 1825 (immutable)
- SEC-25 retention_expires_at column not exposed to PUT

### R5 Audit-log evasion (5)
- SEC-26 Simulated DB error mid-approve: audit row also rolled back (TX integrity)
- SEC-27 audit_logs append-only trigger blocks UPDATE
- SEC-28 audit_logs append-only trigger blocks DELETE
- SEC-29 Approval emits exactly 1 audit row (not 0, not 2)
- SEC-30 Audit log includes IP address from X-Forwarded-For (existing pattern)

### IDOR / cross-tenant generic (10)
- SEC-31 Path-param doc_id from another tenant: GET → 404
- SEC-32 Path-param doc_id from another tenant: POST submit → 404
- SEC-33 Path-param doc_id from another tenant: DELETE → 404
- SEC-34 Body-supplied new_document_id (supersede) from another tenant: trigger blocks
- SEC-35 GET /api/feature-flags/me as tenant B uses tenant A's session token → token's tenant_id authoritative (rejected if mismatch)
- SEC-36 Brute-force doc_id range: rate-limited 10 r/s on /api/documents/*
- SEC-37 Mass-list endpoint /api/documents pagination: no leak across tenant
- SEC-38 GDPR export only exports requestor's tenant data
- SEC-39 Audit log query for tenant A: filtered server-side; client cannot pass tenant_id
- SEC-40 Provider-role auditor cross-tenant doc read: only docs in their assigned submissions

### File upload validation regression (5)
- SEC-41 Upload empty file: 422
- SEC-42 Upload >50MB: 413
- SEC-43 Upload exec/binary disguised as PDF: magic-byte check still runs (existing)
- SEC-44 Upload with path-traversal filename "../etc/passwd": sanitized to safe name
- SEC-45 Upload during pending_approval state of another doc: doesn't affect that doc

### Rate limit / DoS (5)
- SEC-46 /api/documents/{id}/submit-for-approval: 10 r/s burst 20 limit honored
- SEC-47 /api/documents/{id}/versions: depth limit + rate limit prevents amplification
- SEC-48 /api/documents/upload: 2 r/s upload zone (existing)
- SEC-49 Concurrent /approve from 2 sessions on same doc: only first succeeds, second 409
- SEC-50 Massive supersede chain (depth 1000): trigger truncates at 10, response in <500ms

---

## Summary

| Category | Count | Coverage focus |
|---|---:|---|
| UNIT | 50 | State machine + permission + retention + version chain + payload validators + frontend hook |
| INT | 50 | All 6 new endpoints (happy + error + tenant) + DB triggers + audit + migration |
| SMOKE | 50 | Existing endpoints flag-OFF baseline + flag-ON additions + cross-endpoint workflows + service health + frontend renders |
| FUNC | 50 | 5 personas × 6 scenarios + /promote 10-cell matrix + supersede chain + audit completeness |
| UAT | 50 | Gherkin per 6 personas (business owner, member-approver, member-nonapprover, IHC, provider, admin) |
| SEC | 50 | STRIDE: R1 (5) + R2 (5) + R3 (10) + R4 (5) + R5 (5) + IDOR (10) + upload (5) + rate-limit (5) |
| **TOTAL** | **300** | meets methodology floor |

---

## Sign-off

Stage 4 complete when:
- [x] All 6 categories ≥50 cases
- [x] Every spec risk has tests in SEC
- [x] Every existing endpoint has SMOKE test
- [x] Every state transition has UNIT + INT
- [x] Test IDs are stable (used in commit refs + Stage 6 report)

→ Stage 5 (Implementation) once user signs off this plan.
