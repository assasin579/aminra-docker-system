# Feature #24 — Threat Model + Regression Risk

**Stage 2** · linked to `spec.md`. STRIDE for each spec-§11 risk + regression-risk assessment for every existing endpoint that touches `documents`.

## A. STRIDE per spec risk

Severity scale: **C**ritical · **H**igh · **M**edium · **L**ow.

### R1 — Approver elevation (E)
- **Threat**: A user without `can_approve_documents` calls `POST /api/documents/{id}/approve` directly (e.g., crafted JWT, internal service-to-service, or guessed endpoint) and bypasses approval policy.
- **Severity**: **C** (forges audit-grade approval).
- **Mitigations**:
  1. Server-side permission check at endpoint entry: `await check_permission_db(user, "can_approve_documents")` — derives from `users.permissions` JSONB, not client claim.
  2. Endpoint refuses if `approval_status != 'pending_approval'`.
  3. Audit log captures actor + timestamp; non-approver attempt logged as `document.approval_denied`.
  4. Feature-flag-gated: 404 when flag OFF (one less attack surface during rollout).
- **Tests** (Stage 4 Security):
  - SEC-01..05: cross-permission attempts (member without flag, member with flag flipped post-issuance, admin attempting tenant approve, JWT with stale role, expired token)

### R2 — Cross-tenant version-chain leak (I)
- **Threat**: Tenant A creates a doc whose `version_parent_id` points to a tenant B doc (perhaps via crafted POST). Then `GET /versions` recurses across tenants → leaks tenant B's history.
- **Severity**: **C** (multi-tenant breach is the project's #1 invariant).
- **Mitigations**:
  1. `version_parent_id` set ONLY by server during supersede flow — never accepted from client body.
  2. DB constraint considered (FK + check `parent.tenant_id = child.tenant_id`) — schema ADD CONSTRAINT in migration 017.
  3. `/versions` query joins on tenant_id explicitly: `WHERE tenant_id = $1 AND id IN (chain ids)`.
  4. Recursion depth limit (10 levels) to defend against malformed chains.
- **Tests**: SEC-06..10 (parent_id from another tenant rejected, recursive query stays in tenant, depth limit enforced, FK self-reference allowed only same-tenant, /versions returns only same-tenant rows).

### R3 — Status-machine bypass via existing endpoints (T+E)
- **Threat**: Existing `POST /api/documents/{id}/promote` historically sets `status='approved'`. After Phase 1, that bypasses the new state machine (no approver_id, no effective_date, no audit event for approval).
- **Severity**: **H** — silently invalidates compliance audit.
- **Mitigations**:
  1. Modify `/promote` behaviour when feature flag is ON: it still sets internal `status='approved'` (backwards compat for callers) BUT also sets `approval_status='approved'`, attributes `approver_id=<actor>`, `approved_at=NOW()`, and emits `document.approved` audit event. This effectively folds /promote into the new state machine.
  2. When flag OFF: `/promote` behaves exactly as today (no schema additions touched).
  3. Reject `/promote` if doc is in `pending_approval` (must use new `/approve` endpoint to set approver context).
- **Tests**: FUNC-21..25 (flag-on /promote sets approval fields, flag-on /promote in pending state rejects, flag-off /promote unchanged, audit log emitted, JWT user becomes approver_id).

### R4 — Retention tampering (T)
- **Threat**: Approver sets `retention_period_days=1` to fast-track deletion of an inconvenient doc.
- **Severity**: **H** — destroys evidence required for halal compliance audit.
- **Mitigations**:
  1. Server-side floor: `retention_period_days >= 1825` (5 years) — reject body with smaller values; 422 with explicit error.
  2. Once approved, `retention_period_days` is IMMUTABLE (no PUT endpoint to change). Future Phase 2 may add an admin-only override with audit trail; not in v1.
  3. Audit log captures the value at approval time so any subsequent direct-DB manipulation is detectable in retro.
- **Tests**: SEC-11..13 (POST approve with retention<1825 → 422; PUT attempt to change after approve → 405; DB-level audit-log entry includes retention).

### R5 — Audit-log evasion (R)
- **Threat**: Approval action succeeds but audit_log row is missing (e.g., transactional rollback after audit insert OR audit insert wrapped in try/except that swallows error).
- **Severity**: **H** — non-repudiation broken; if regulator asks "who approved at when", we can't prove.
- **Mitigations**:
  1. Audit-log insert in SAME transaction as approval mutation: either both commit or both rollback.
  2. Audit-log table is append-only (existing trigger from migration 007 prevents UPDATE/DELETE).
  3. Service helper `log_audit(...)` raises on failure, NOT swallowed.
  4. Per-feature smoke test verifies audit row exists after every state transition.
- **Tests**: INT-31..36 (transactional integrity: simulated DB error mid-approve → no audit row + no status change; happy path: 1 audit row per transition; obsolete event recorded).

### R6 — Existing endpoint response-shape regression (quality)
- **Threat**: Adding columns to `documents` causes existing `GET /api/documents` or `GET /api/documents/{id}` to leak new fields when feature flag is OFF, breaking frontends that don't expect them.
- **Severity**: **M** — internal frontend will tolerate; third-party API consumers (none today, but mobile app reads same routes) might break.
- **Mitigations**:
  1. Existing endpoints read explicit column lists: `SELECT id, filename, ..., status FROM documents` — adding columns to table doesn't expand response.
  2. New fields included ONLY when feature flag is ON (server-side check).
  3. Pydantic response models (`DocumentDetail`, `DocumentListResponse`) keep existing field set; add Optional new fields with default exclude_none.
  4. Snapshot test of `GET /api/documents/{id}` body when flag OFF — must equal pre-Phase-1 baseline byte-for-byte.
- **Tests**: SMOKE-41..50 (flag-off response identical for 10 fixture docs; flag-on adds fields; mobile/auditor app fixture compatible).

### R7 — Migration backfill error (T)
- **Threat**: Migration 017 maps `status='approved'` rows to `approval_status='approved'`, but rows with edge `status` values (`uploaded` mapped to draft? `rejected` mapped to draft?) get wrong default → workflow inconsistency.
- **Severity**: **M** — recoverable but creates noise.
- **Mitigations**:
  1. Backfill rules explicit in migration UP block (per spec §4):
     - `status='approved'` → `approval_status='approved'`, version=1, approver_id=reviewed_by, approved_at=reviewed_at
     - `status IN ('uploaded', 'reviewing')` → `approval_status='draft'`, version=1
     - `status='rejected'` → `approval_status='draft'`, version=1
     - All retention=1825d default
  2. Migration UP runs in single transaction; rollback on any constraint violation.
  3. Post-migration verification query in runbook: count rows per (status, approval_status) cross-tab should match expected matrix.
- **Tests**: INT-37..40 (4 backfill scenarios: approved, uploaded, rejected, mixed); MIG-01..05 (apply, verify counts, rollback, re-apply, idempotent).

### R8 — Frontend hook race (quality)
- **Threat**: `useFeature("document_versioning_v1")` returns false during initial fetch; UI hides approval section even for an authenticated approver. Approver thinks feature isn't deployed.
- **Severity**: **L** — cosmetic.
- **Mitigations**:
  1. `useFeatureFlags()` returns `isLoading` flag; UI shows skeleton (not "feature off") while pending.
  2. Provider hydrates BEFORE first render of doc detail page (route-level data fetch).
  3. Closed-default policy means: if fetch errors, treat as off; toast logged for diagnostic.
- **Tests**: UNIT-21..24 frontend (hook loading state; SSR safety; error fallback).

---

## B. Additional STRIDE not yet in spec

### S — Spoofing approver identity in audit log
- Audit log stores `user_id` from JWT `sub`. JWT signing key rotation → tokens re-issued. Old token accepted briefly (cache TTL on jwt_secret) → replay risk.
- Mitigation: JWT_SECRET in Vault; verify exp + nbf; revocation list for compromised tokens (existing).
- Tests: SEC-14 (expired token → 401 on /approve).

### D — DoS via /versions recursion
- Crafted long version chain (10k self-references via direct DB write) hits `/versions` → CPU spike.
- Mitigation: depth limit 10 (R2 mitigation #4); rate-limit zone `/api/documents/*/versions` at nginx (5 r/s burst 10).
- Tests: SEC-15..16 (rate-limit blocks burst >10; depth limit returns truncated chain + warning header).

### E — Direct DB write bypassing API
- Attacker with DB credentials (or compromised service account) could insert approval row.
- Mitigation: out of scope for app-layer; defended by Vault credential rotation + IAM. Document in runbook.

---

## C. Regression risk — every existing endpoint touching `documents`

Source survey (file:line):
| Endpoint | File:line | Behavior change risk | Test coverage to add |
|---|---|---|---|
| `GET /api/documents` | document_router.py:130 | Response shape — see R6 mitigation. SELECT explicit cols. | SMOKE-41 flag-off shape; SMOKE-42 flag-on shape includes new fields |
| `GET /api/documents/revisions/{doc_type_id}` | document_router.py:225 | Reads documents by `doc_type` filter; returns version-grouped list. New fields propagate via response model. | SMOKE-43 flag-off; SMOKE-44 flag-on with version chain visible |
| `POST /api/documents/{doc_id}/promote` | document_router.py:279 | **Highest risk** per R3. Behaviour changes when flag ON. | FUNC-21..25 (R3 tests); SMOKE-45 flag-off baseline |
| `GET /api/documents/{doc_id}` | document_router.py:309 | Detail response — add new optional fields. | SMOKE-46 byte-equal flag-off; SMOKE-47 flag-on includes fields |
| `GET /api/documents/{doc_id}/preview` | document_router.py:356 | File preview; no schema interaction. | SMOKE-48 unchanged |
| `GET /api/documents/{doc_id}/file` | document_router.py:473 | Raw file download. | SMOKE-49 unchanged |
| `POST /api/documents/upload` | document_router.py:519 | Insert new doc. New columns default NULL → no impact. | INT-41 upload still works flag-off; INT-42 flag-on sets approval_status='draft' |
| `POST /api/documents/{doc_id}/evaluate` | document_router.py:657 | LLM evaluation; touches `evaluation_result` JSONB only. | SMOKE-50 unchanged |
| `DELETE /api/documents/{doc_id}` | document_router.py:700 | Hard delete. Need to verify version chain integrity (orphan parent_id refs). | INT-43 deleting child unlinks parent; INT-44 deleting parent in chain — propagate or block? |
| `GET /api/dashboard/stats` | document_router.py:752 | Aggregate counts. May now include `approval_status` breakdown. | SMOKE flag-off counts equal baseline |
| `POST /api/submissions/submit` | submission_router.py:325 | Sets `submission.document_ids = [...]`. Doesn't read approval state today. **Decision**: keep existing behavior in v1; later phase may require approved-only docs in submissions. | INT-45 submit with mixed-status docs allowed in v1 |
| `services/data_export.py:155` | data_export.py:155 | GDPR export — uses `_rows()` helper. New fields auto-included. **PII risk**: approver name, dates — fine since exporting user owns the docs. | INT-46 GDPR export includes new fields when flag ON |

### C.1 Decision matrix on `/promote` (R3)

| State of doc | flag OFF | flag ON |
|---|---|---|
| status=`uploaded`, approval_status=NULL or `draft` | sets `status='approved'` (legacy) | sets `status='approved'`, `approval_status='approved'`, `approver_id=actor`, `approved_at=NOW()`, `effective_date=NOW().date()`, retention=1825; emit audit `document.approved` |
| status=`approved` | no-op (idempotent) | no-op |
| status=`rejected` | sets to `approved` (legacy quirk) | rejected — must re-submit via new flow; 409 with explanation |
| status=`reviewing` | sets to `approved` (legacy) | rejected — must use `/approve` endpoint with explicit dates; 409 |
| approval_status=`pending_approval` | (didn't exist before) | rejected — use `/approve`; 409 |

Test coverage: 5 cells × flag-on/off = 10 tests minimum (FUNC-21..30).

---

## D. Cross-cutting risks

| # | Concern | Mitigation |
|---|---|---|
| X1 | Database load on `/versions` (recursive CTE) | Materialized view? — defer Phase 2; v1 uses recursive CTE with depth ≤ 10 limit |
| X2 | Breaking mobile auditor app (consumes `/api/documents/{id}` for read-only review) | Spec §6 requires response shape unchanged when flag OFF; mobile reads as a Provider role → flag visibility check |
| X3 | Sentry frontend error spike if hook race | useFeature SSR-safe + closed-default; ErrorBoundary around `/documents/{id}` route |
| X4 | Audit log volume (each transition = 1 row; high-velocity tenants might bloat) | audit_logs already partitioned by created_at; retention policy in audit_log_router (existing); not feature-specific |

---

## E. Sign-off

Before Stage 3 (Schema design), Stage 2 must establish:

- [x] Each spec risk mapped to mitigation + test class
- [x] Severity rated (no Critical without explicit justification)
- [x] All existing endpoints reviewed for regression risk
- [x] `/promote` decision matrix locked
- [x] Cross-cutting risks (X1..X4) acknowledged

Open Stage 2 questions:
1. **DELETE doc with chain children**: block or unlink? — Currently lean toward BLOCK (cleaner audit trail; force user to supersede first). Confirm in Stage 3 or revisit at expert consult.
2. **Submission with non-approved docs**: keep allowing (v1) or require approval? — Lean toward keep for v1; flag for expert consult.
3. **DB-level FK `parent.tenant_id = child.tenant_id` constraint**: enforce now or defer? — Recommend enforce in migration 017 (cheap to add, eliminates R2 root cause).

→ Proceed to Stage 3 (Schema design) once user signs off these 3 open questions.
