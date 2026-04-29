# Feature #24 — Document Version Control Hardening

**Status**: Stage 1 (Spec) · Phase 1 Tier-1a · Started 2026-04-29
**Owner**: Halal MVP team
**Feature flag**: `document_versioning_v1` (seeded disabled in migration 016)

## 1. Why this exists

JAKIM MS 1500:2019 §5.5 (Documented Information) requires:

| Clause | Requirement | Currently in AMINRA | Gap |
|---|---|---|---|
| §5.5.1 | Documents controlled before issue (formal approval) | `documents.status` only `uploaded/reviewing/approved/rejected` — no signed approver, no effective_date | YES |
| §5.5.2 | Documents reviewed periodically | No `next_review_date` | YES |
| §5.5.3 | Changes identified + traceable across versions | No version_parent chain; one-shot rows | YES |
| §5.5.6 | Obsolete documents prevented from unintended use | No `superseded_by` link, no obsolete state | YES |
| §5.5.7 | Retention as required (typically 5 years for halal compliance) | No `retention_period` field | YES |

Without this, JAKIM/BPJPH external audit will fail on document-control evidence — even if each individual doc looks correct.

## 2. Out of scope

- Multi-language document content (separate i18n concern)
- Document-content diffing UI (visual diff between versions) — defer to Phase 2 nice-to-have
- Automated retention-deletion job — Phase 1 will only TRACK retention; deletion follows in a later sprint

## 3. Personas + permissions

Reuse existing AMINRA roles (no new schema for permissions):

| Persona | Can submit for approval | Can approve/reject | Can supersede | Can view versions |
|---|---|---|---|---|
| Business Owner | ✓ (own tenant) | ✓ (own tenant) | ✓ | ✓ |
| Business Member with `can_approve_documents` permission | ✓ | ✓ | ✗ | ✓ |
| Business Member without that permission | ✓ | ✗ | ✗ | ✓ |
| Internal Halal Committee member (ihc_role IS NOT NULL) | ✓ | ✓ (delegated approver — JAKIM §5.4 IHC oversight) | ✓ | ✓ |
| Provider / Auditor (cross-tenant) | ✗ | ✗ | ✗ | ✓ READ ONLY (when reviewing a submission they own) |
| Admin | ✗ | ✗ | ✗ | ✓ READ ONLY (audit trail purposes) |

`can_approve_documents` is a NEW permission flag — additive (default false on existing users; tenant owners get it automatically).

## 4. State machine

```
            ┌────────┐  submit     ┌─────────────────┐  approve   ┌──────────┐
upload ──→  │ draft  │ ──────────→ │ pending_approval│ ─────────→ │ approved │
            └────────┘             └─────────────────┘            └──────────┘
                ▲                          │                            │
                │   reject                 │                            │ supersede (creates new doc, this becomes obsolete)
                └──────────────────────────┘                            ▼
                                                                  ┌──────────┐
                                                                  │ obsolete │
                                                                  └──────────┘
```

### Allowed transitions
- `draft → pending_approval` — actor: any user with `can_edit` on this doc; emits `document.submitted_for_approval` audit event
- `pending_approval → draft` — actor: original submitter or approver (rejection with reason); audit `document.approval_rejected`
- `pending_approval → approved` — actor: user with `can_approve_documents`; sets `approver_id`, `approved_at`, `effective_date` (default = today, override allowed); audit `document.approved`
- `approved → obsolete` — automatic when another doc sets `superseded_by_id = this.id`; audit `document.superseded`

### Forbidden transitions (must return 409)
- `draft → approved` (skip approval) — even owners
- `approved → draft` (un-approve)
- `obsolete → anything` — terminal state
- `approved → pending_approval` (must use supersede flow)

### Backwards compatibility (existing rows)
Existing documents at migration time:
- `status = 'approved'` → `approval_status = 'approved'`, `version_number = 1`, `approver_id = reviewed_by` (already exists), `approved_at = reviewed_at`
- `status = 'uploaded' OR 'reviewing'` → `approval_status = 'draft'`, `version_number = 1`
- `status = 'rejected'` → `approval_status = 'draft'`, `version_number = 1`
- All get `retention_period_days = 1825` (5y) default; `effective_date = NULL`; `next_review_date = NULL`

## 5. Multi-tenant boundary

ALL new endpoints filter by `tenant_id` from JWT. Cross-tenant access is forbidden EXCEPT:
- Provider/auditor reading a doc that's part of a `submission` they're assigned to (existing pattern — reuse, do not duplicate auth check)
- Admin read-only on audit trails (existing pattern)

Critical invariant: a business owner of tenant A cannot:
- View, approve, reject, or supersede docs in tenant B
- See tenant B docs in version chain history

This must be tested explicitly (Stage 4 Security tests).

## 6. API surface

All routes mounted at existing `/api` prefix. Feature-flagged behind `document_versioning_v1`: when flag is OFF, new routes return 404; when ON, available.

| Method | Path | Purpose | Auth | Body |
|---|---|---|---|---|
| GET | `/api/documents/{id}/versions` | Full version chain (oldest → newest) | tenant member | — |
| POST | `/api/documents/{id}/submit-for-approval` | Move draft → pending_approval | tenant member with `can_edit` | `{}` |
| POST | `/api/documents/{id}/approve` | Move pending → approved | tenant approver | `{ effective_date?: ISO date, next_review_date?: ISO date, retention_period_days?: int }` |
| POST | `/api/documents/{id}/reject` | Move pending → draft (with reason) | tenant approver | `{ reason: string (≤500 chars) }` |
| POST | `/api/documents/{id}/supersede` | Mark obsolete + link new version | tenant owner OR IHC | `{ new_document_id: UUID }` |
| GET | `/api/documents/{id}/approval-status` | Current approval state + approver + dates | tenant member | — |

Existing routes (`/api/documents`, `/api/documents/{id}`, etc.) are NOT modified — only EXTEND response shape with new optional fields when flag is ON. When flag OFF, existing response unchanged.

### Response shape (additive on existing GET `/api/documents/{id}`)
New optional fields (null if flag OFF or not yet set):
```json
{
  "version_number": 1,
  "version_parent_id": null,
  "approval_status": "approved",
  "approver_id": "uuid",
  "approver_name": "Nguyen Van A",
  "approved_at": "2026-01-15T10:00:00Z",
  "effective_date": "2026-01-20",
  "next_review_date": "2027-01-20",
  "retention_period_days": 1825,
  "retention_expires_at": "2031-01-15T10:00:00Z",
  "superseded_by_id": null,
  "is_obsolete": false
}
```

## 7. UI surface

Frontend page `/documents/{id}` extension (only when `useFeature("document_versioning_v1")` returns true):

1. **Approval status badge** at top of card: `Bản nháp` / `Chờ duyệt` / `Đã phê duyệt` / `Đã thay thế` (color: navy/amber/green/gray).
2. **Approval block** (visible when approved):
   - Người phê duyệt: {approver_name} on {approved_at}
   - Hiệu lực từ: {effective_date}
   - Đánh giá lại: {next_review_date}  (red if past)
   - Lưu trữ đến: {retention_expires_at}
3. **Action buttons** (role-conditional):
   - "Trình duyệt" (when status=draft, role=can_edit)
   - "Phê duyệt" / "Từ chối" (when status=pending_approval, role=approver)
   - "Thay thế bằng phiên bản mới" (when status=approved, role=owner/IHC)
4. **Version history drawer**: list all versions in chain with status badges + dates.
5. **Approval modal**: form for approver to set effective_date (default today), next_review_date (default +1y), retention_period_days (default 1825).

Toast on each transition. Audit-log link visible to admin.

## 8. Audit log events (extend existing `audit_logs` table)

| event_action | actor | entity | metadata |
|---|---|---|---|
| `document.submitted_for_approval` | submitter | doc | `{prev_status, new_status}` |
| `document.approved` | approver | doc | `{effective_date, next_review_date, retention_period_days}` |
| `document.approval_rejected` | approver | doc | `{reason}` |
| `document.superseded` | actor | old doc | `{new_document_id, version_chain_depth}` |

All entries reference `tenant_id` so cross-tenant queries are scoped.

## 9. Acceptance criteria (Definition of Done — feature level)

- [ ] Migration 017 applied + reversible (UP + DOWN both tested)
- [ ] All 6 new endpoints work behind feature flag (404 when OFF, functional when ON)
- [ ] State machine enforces forbidden transitions (returns 409 with body explaining why)
- [ ] Cross-tenant isolation verified: tenant A cannot read/mutate tenant B's docs across all 6 endpoints
- [ ] Existing `/api/documents` endpoints unchanged in response shape when flag OFF (zero regression)
- [ ] Frontend renders new fields only when `useFeature("document_versioning_v1")` is true
- [ ] Audit log emits 4 new event types correctly
- [ ] Backwards compat: existing 'approved' rows auto-mapped to `approval_status='approved'` on migration upgrade
- [ ] ≥300 tests pass (50 × 6 categories per methodology)
- [ ] Coverage not lower than baseline
- [ ] Bandit, gitleaks, npm/pip-audit clean
- [ ] Docs: spec, threat-model, schema, test-plan, test-report, runbook
- [ ] Health check post-each-commit (per methodology section J)
- [ ] Test data cleanup post-feature (per methodology section I)

## 10. Open questions for review (before Stage 2)

1. **`can_approve_documents` permission**: should it default to ON for tenant owners only, or ALL members?
   → **Decision**: ON for owners; OFF for members; tenant owner can grant via existing member-permission UI.
2. **Approval delegation**: can owner delegate to a non-IHC member temporarily (e.g., when on leave)?
   → **Decision**: not in v1. Owner can flip member permission ON/OFF anytime; that's the workaround.
3. **`effective_date` in past**: allow backdating? (e.g., approver finalizes a doc that was operationally effective last month)
   → **Decision**: allow, but emit a warning toast on UI; audit log captures the gap. SME may revisit at expert consult.
4. **Retention countdown start**: from `approved_at` or `effective_date`?
   → **Decision**: from `effective_date` if set, else `approved_at`. JAKIM requires retention from "date of issue" — `effective_date` is the more accurate proxy.
5. **Supersede with new file**: must the new doc be already uploaded, or can supersede flow create new doc inline?
   → **Decision**: must be already uploaded (separate upload + link step). Keeps mutation atomic + matches existing upload UX.

## 11. Risks (input to Stage 2 STRIDE)

- **R1**: Approver elevation — non-approver bypasses to approve via direct DB or another endpoint
- **R2**: Cross-tenant version-chain leak — tenant A's superseded doc might show in tenant B's history if FK accidentally crosses tenants
- **R3**: Status-machine bypass — direct PUT to status field (existing endpoints) skipping new state machine
- **R4**: Retention tampering — user reduces `retention_period_days` after approval to delete sooner
- **R5**: Audit-log evasion — approval action without audit_log entry
- **R6**: Existing endpoints' response shape regression when feature flag is OFF
- **R7**: Migration backfill error — rows with edge-case `status` values mapped wrong
- **R8**: Frontend hook race — `useFeature` returns false before fetch resolves, hides approval UI for an authenticated approver

Each must have explicit Stage 4 test cases.

---

**Sign-off for Stage 1 (Spec)**: Ready when reviewer agrees:
- Persona/permission matrix correct
- State machine covers all real workflows
- Multi-tenant boundary explicit
- Open questions answered
- Acceptance criteria measurable

→ Proceed to Stage 2 (Threat model + regression risk).
