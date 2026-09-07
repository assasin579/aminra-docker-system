# AMINRA Supply Chain P0/P1 Implementation Plan

> **For Hermes/Claude:** Use `subagent-driven-development` to implement task-by-task with strict TDD. No production code before a failing test. Do not commit/push/deploy unless the founder explicitly authorizes.

**Goal:** Upgrade AMINRA supply-chain from demo traceability to pilot-grade Halal manufacturing traceability where CB-authoritative supplier eligibility, raw-material lots, QC release, batch gates, process controls, and recall linkage are enforced across BE, FE, DB, and UAT.

**Architecture:** Keep the current FastAPI modular-monolith + PostgreSQL/Alembic + Next.js App Router stack. Add new normalized tables and services around the existing `suppliers`, `materials`, `process_templates`, `production_batches`, `batch_materials`, and `batch_steps` model. Supplier Halal eligibility is controlled by Certification Body data; AMINRA must project and enforce it, not internally “verify” supplier Halal certificates.

**Tech Stack:** FastAPI, asyncpg, Pydantic, PostgreSQL/Alembic, pytest, Next.js 16, TypeScript, Vitest, Playwright, Docker Compose.

---

## Success Criteria

### P0 success criteria

1. Business users only see/select NCC/materials that are CB-authorized and currently effective.
2. Batch creation consumes specific released raw-material lots, not only material master records.
3. Expired/suspended/revoked supplier eligibility blocks new batch use.
4. Incoming raw-material lots require QC release before production use.
5. Batch QA release/seal is blocked unless all required critical steps, checklist items, material-lot gates, and open deviations pass.
6. Public trace is only available for QA-released + sealed batches.
7. Recall query can trace one-up/one-down: raw material lot → affected production batches → finished goods/shipment placeholders.
8. Database migrations have upgrade + downgrade and pass empty-schema migration tests.
9. BE unit/functional/integration tests cover success, edge, failure, RBAC, and tenant-boundary cases.
10. FE unit/contract/e2e tests cover list/filter/forms/disabled states/error copy/public trace behavior.
11. Smoke/UAT report exists with evidence and explicit GO/PARTIAL/NO-GO verdict.

### P1 success criteria

1. SOP/process templates have document-control status, version, approval metadata, effective dates, and immutable version snapshot on batch.
2. Process steps support criticality, parameter limits, required evidence, and role requirements.
3. Supplier Approved List export exists and includes only eligible/current records.
4. Document expiry alerts exist for supplier eligibility/certificates and raw-material lot documents.
5. Inventory balance supports basic receive/release/consume/adjust with FEFO suggestions.
6. Finished goods lot and shipment/customer linkage support recall drill reporting.
7. E-signature records include user_id, role, timestamp, reason, action, and payload hash for QA-critical actions.

---

## Domain Model Principles

1. **CB is the authority for NCC Halal eligibility.** AMINRA does not self-verify NCC Halal certs.
2. **Material master is not traceability.** Traceability must use actual raw-material lots.
3. **Production completion is not QA release.** Add a separate QA/Halal release gate.
4. **Public trace must be fail-closed.** No public trace for draft/in-progress/unreleased/unsealed batches.
5. **Delete must preserve trace.** Prefer archive/suspend over hard delete for any object used by production.
6. **Tenant boundaries are P0 security requirements.** Every new route and file/evidence read path needs negative tests.
7. **No free-text for governed statuses.** Use enums or constrained schemas for supplier type, eligibility status, lot status, batch status, criticality, deviation status.

---

# P0 Implementation Plan

## P0-A — CB-authoritative Supplier/NCC Eligibility

### Task P0-A1: Add DB schema for CB supplier eligibility

**Objective:** Store CB-controlled supplier eligibility without treating AMINRA/business as verifier.

**Files:**
- Create: `backend/alembic/versions/0xx_supplier_eligibility.py`
- Test: `backend/tests/test_migrations_supplier_eligibility.py`

**DB objects:**
- `supplier_eligibilities`
  - `id uuid primary key`
  - `tenant_id uuid not null`
  - `supplier_id uuid not null references suppliers(id)`
  - `cb_id uuid null references users(id)` or provider-org equivalent
  - `certificate_no varchar(255) not null`
  - `issuer_name varchar(255) not null`
  - `valid_from timestamptz not null`
  - `valid_until timestamptz not null`
  - `status supplier_eligibility_status not null default 'active'`
  - `scope jsonb not null default '{}'`
  - `source_of_truth varchar(100) not null default 'cb'`
  - `created_by uuid null`
  - `updated_by uuid null`
  - timestamps
- Enum: `active | expired | suspended | revoked`
- Indexes:
  - `(tenant_id, supplier_id)`
  - `(tenant_id, status, valid_until)`
  - unique partial active cert if appropriate: `(tenant_id, supplier_id, certificate_no)`

**TDD:**
1. Write migration test: fresh DB can upgrade/downgrade.
2. Write schema test: status enum rejects unknown value.
3. Write FK test: eligibility cannot reference missing supplier.
4. Write tenant/index existence test.

**Verification commands:**
- `docker compose exec aminra-backend pytest backend/tests/test_migrations_supplier_eligibility.py -v`
- `docker compose exec aminra-backend alembic upgrade head`
- `docker compose exec aminra-backend alembic downgrade -1 && docker compose exec aminra-backend alembic upgrade head`

### Task P0-A2: Add Pydantic schemas and eligibility service

**Objective:** Centralize eligibility calculation: active + within valid date + CB source + scope match.

**Files:**
- Modify: `backend/supply_chain/models.py`
- Create: `backend/supply_chain/eligibility_service.py`
- Test: `backend/tests/test_supplier_eligibility_service.py`

**Required functions:**
- `is_supplier_eligible(db, tenant_id, supplier_id, at_time, material_category=None) -> bool`
- `list_eligible_suppliers(db, tenant_id, at_time, material_category=None)`
- `assert_supplier_eligible(...)` raises `HTTPException(409)` with user-safe reason.

**TDD cases:**
1. Active + date valid → eligible.
2. Expired date → ineligible.
3. Suspended/revoked → ineligible.
4. Future valid_from → ineligible.
5. Wrong tenant → ineligible.
6. Scope mismatch → ineligible.
7. Missing eligibility row → ineligible.

### Task P0-A3: Replace supplier list behavior with eligible projection where business selects NCC

**Objective:** Business-facing NCC selection should only show eligible/current NCC by default.

**Files:**
- Modify: `backend/supply_chain/supplier_router.py`
- Modify: `backend/supply_chain/material_router.py` if supplier filter feeds material creation.
- Test: `backend/tests/test_supply_chain_supplier_eligibility_routes.py`

**API design:**
- Existing `/suppliers` can keep admin/master list if needed.
- Add `/suppliers/eligible` or query `?eligible_only=true` for production selection.
- Business material/batch selectors must use eligible-only endpoint.

**TDD cases:**
1. Eligible supplier appears.
2. Expired supplier hidden.
3. Suspended supplier hidden.
4. Supplier with uploaded cert but no CB eligibility hidden.
5. Cross-tenant eligible supplier hidden.
6. Provider/business role boundary enforced.

### Task P0-A4: Add FE eligible supplier selection and warning states

**Objective:** FE must not let users select ineligible NCC in material/batch setup.

**Files:**
- Modify: `frontend/aminra-web/app/supply-chain/materials/page.tsx`
- Modify: `frontend/aminra-web/app/supply-chain/batches/page.tsx`
- Add/modify tests under `frontend/aminra-web/__tests__/` or nearest test convention.

**FE behavior:**
- Supplier dropdown calls eligible endpoint.
- Ineligible suppliers hidden from create flows.
- Existing material with now-ineligible supplier displays warning badge, not silent failure.
- Copy: “NCC này không còn hiệu lực theo dữ liệu tổ chức chứng nhận.”

**Tests:**
- Vitest/source contract: component calls eligible endpoint.
- Functional FE test: expired supplier is not selectable.
- Playwright: user cannot create batch with hidden/suspended NCC.

---

## P0-B — Raw Material Lots + Incoming QC Release

### Task P0-B1: Add raw material lot DB schema

**Objective:** Track actual received material lots.

**Files:**
- Create: `backend/alembic/versions/0xy_raw_material_lots.py`
- Test: `backend/tests/test_migrations_raw_material_lots.py`

**DB objects:**
- `raw_material_lots`
  - `id uuid primary key`
  - `tenant_id uuid not null`
  - `material_id uuid not null references materials(id)`
  - `supplier_id uuid not null references suppliers(id)`
  - `supplier_lot_no varchar(255) not null`
  - `internal_lot_no varchar(255) not null`
  - `received_date date not null`
  - `mfg_date date null`
  - `expiry_date date null`
  - `received_qty numeric(18,6) not null check > 0`
  - `available_qty numeric(18,6) not null check >= 0`
  - `unit varchar(50) not null`
  - `status raw_material_lot_status not null default 'pending_qc'`
  - `storage_location varchar(255) null`
  - `halal_status varchar(50) not null default 'pending'`
  - `released_by uuid null`
  - `released_at timestamptz null`
  - `rejected_by uuid null`
  - `rejected_at timestamptz null`
  - `coa_file_path text null`
  - `incoming_inspection jsonb not null default '{}'`
  - timestamps
- Enum: `pending_qc | quarantined | released | rejected | expired | consumed`
- Unique: `(tenant_id, internal_lot_no)`

### Task P0-B2: Add raw-material lot API

**Objective:** CRUD + release/reject lots safely.

**Files:**
- Create: `backend/supply_chain/raw_material_lot_router.py`
- Modify: `backend/main.py` or supply-chain router registration file.
- Modify: `backend/supply_chain/models.py`
- Test: `backend/tests/test_supply_chain_raw_material_lots.py`

**Routes:**
- `GET /supply-chain/raw-material-lots`
- `POST /supply-chain/raw-material-lots`
- `GET /supply-chain/raw-material-lots/{id}`
- `PUT /supply-chain/raw-material-lots/{id}` for non-release fields while not consumed.
- `POST /supply-chain/raw-material-lots/{id}/release`
- `POST /supply-chain/raw-material-lots/{id}/reject`

**TDD cases:** minimum 60 targeted cases covering:
- required fields
- date boundaries
- negative quantity
- duplicate internal lot no
- material/supplier same-tenant check
- supplier eligibility required before release
- expired lot cannot release
- released lot cannot be edited destructively
- consumed lot cannot be deleted
- provider cannot access business lot
- cross-tenant read/update/delete denied

### Task P0-B3: Add FE raw-material lot receiving page

**Objective:** Warehouse/QA can register, inspect, release/reject lots.

**Files:**
- Create: `frontend/aminra-web/app/supply-chain/raw-material-lots/page.tsx`
- Modify navigation/sidebar for supply-chain if present.
- Tests: source/Vitest + Playwright.

**FE behavior:**
- List lots with status badges.
- Create receipt form.
- Release/reject actions gated by permission.
- Warnings for expired/near-expiry lots.
- Search by internal lot, supplier lot, material, supplier.

**Tests:**
- Contract: route exists and uses raw-material lot API.
- Functional: pending lot can be released by authorized user.
- Negative: lower permission user sees disabled release.

---

## P0-C — Batch Material Consumption by Lot

### Task P0-C1: Migrate `batch_materials` to reference raw material lots

**Objective:** Batch material usage must point to actual raw-material lots.

**Files:**
- Create: `backend/alembic/versions/0xz_batch_material_lots.py`
- Test: `backend/tests/test_migrations_batch_material_lots.py`

**DB changes:**
- Add `raw_material_lot_id uuid references raw_material_lots(id)` to `batch_materials`.
- Keep `material_id` initially for compatibility, but make service require lot id for new batch creation.
- Add indexes on `(batch_id)`, `(raw_material_lot_id)`.
- Add `consumed_qty`, or reuse `quantity`.

**Compatibility:** existing demo batches may have `raw_material_lot_id null`; new API rejects null unless explicit migration/demo flag.

### Task P0-C2: Enforce lot eligibility and inventory at batch creation/update

**Objective:** Block invalid material lots and decrement available quantity transactionally.

**Files:**
- Modify: `backend/supply_chain/batch_router.py`
- Create: `backend/supply_chain/inventory_service.py`
- Test: `backend/tests/test_batch_material_lot_gates.py`

**Rules:**
- Lot must belong to tenant.
- Lot status must be `released`.
- Lot expiry must be null or after production/release date.
- Supplier eligibility must be active at production time.
- Requested quantity <= available_qty.
- Consume quantity transactionally to avoid race oversell.

**TDD cases:**
1. Released lot with enough qty succeeds.
2. Pending QC lot blocked.
3. Rejected lot blocked.
4. Expired lot blocked.
5. Ineligible supplier blocked.
6. Insufficient qty blocked.
7. Concurrent consume cannot make available_qty negative.
8. Cross-tenant lot blocked.
9. Batch delete/cancel restores quantity only if not QA released.

### Task P0-C3: Update FE batch creation to select raw-material lots

**Objective:** User selects material lot, not only material master.

**Files:**
- Modify: `frontend/aminra-web/app/supply-chain/batches/page.tsx`
- Tests: FE contract + Playwright.

**FE behavior:**
- Material line selector shows: material name, supplier, internal lot, expiry, available qty, status.
- Only released lots are selectable.
- FEFO-sorted by expiry date.
- Display why no lot is available.

---

## P0-D — Batch QA Release, Seal Gates, and Public Trace Fail-Closed

### Task P0-D1: Extend batch statuses and release metadata

**Objective:** Separate production completion from QA/Halal release.

**Files:**
- Create: `backend/alembic/versions/0xa_batch_release_lifecycle.py`
- Modify: `backend/supply_chain/models.py`
- Test: `backend/tests/test_batch_release_lifecycle_migration.py`

**Statuses:**
- `draft`
- `scheduled`
- `in_production`
- `production_completed`
- `qa_hold`
- `qa_released`
- `rejected`
- `shipped`
- `recalled`

**Columns:**
- `qa_released_by uuid null`
- `qa_released_at timestamptz null`
- `release_notes text null`
- `public_trace_enabled boolean not null default false`

### Task P0-D2: Add release gate validator

**Objective:** One central validator determines whether batch can be released/sealed.

**Files:**
- Create: `backend/supply_chain/batch_release_service.py`
- Modify: `backend/supply_chain/batch_router.py`
- Test: `backend/tests/test_batch_release_gates.py`

**Gate checks:**
- All required steps completed.
- All critical steps approved.
- Required checklist items checked.
- Required photo/evidence exists when step requires evidence.
- Material lots valid and still eligible.
- No open deviations P0/P1.
- Output quantity/yield present if configured.

**TDD cases:** at least 40 cases including each gate fail independently.

### Task P0-D3: Update seal/approve behavior to hard-block incomplete batches

**Objective:** Seal only immutable, QA-released batch snapshots.

**Files:**
- Modify: `backend/supply_chain/batch_router.py`
- Test: `backend/tests/test_batch_sealing_hard_blocks.py`

**Rule:** `approve_batch`/seal returns `409` if any release gate fails. It must not merely return `unapproved_steps` as warning.

### Task P0-D4: Public trace only for QA-released + sealed batches

**Objective:** Prevent buyer/auditor from seeing unreleased/in-progress data as trusted trace.

**Files:**
- Modify: `backend/supply_chain/batch_router.py` trace endpoint.
- Modify: `frontend/aminra-web/app/trace/[code]/page.tsx`
- Test: BE trace tests + Playwright public trace.

**TDD cases:**
- Draft returns 404 or not-ready response.
- In production returns not-ready.
- Production completed but not QA released returns not-ready.
- QA released but not sealed returns not-ready.
- QA released + sealed returns trace.
- Integrity mismatch returns warning/fail state.

---

## P0-E — Deviations / Non-Conformance / CAPA Minimal

### Task P0-E1: Add deviation schema

**Objective:** Capture out-of-spec events linked to batch/step/material lot.

**Files:**
- Create: `backend/alembic/versions/0xb_deviations.py`
- Test: migration tests.

**DB objects:**
- `deviations`
  - `id`
  - `tenant_id`
  - `batch_id null`
  - `batch_step_id null`
  - `raw_material_lot_id null`
  - `severity p0|p1|p2|p3`
  - `status open|under_review|closed|voided`
  - `description`
  - `immediate_action`
  - `root_cause`
  - `capa_action`
  - `created_by`
  - `closed_by/closed_at`

### Task P0-E2: Add deviation API and release blocking

**Objective:** Open P0/P1 deviations block QA release.

**Files:**
- Create: `backend/supply_chain/deviation_router.py`
- Modify: `backend/supply_chain/batch_release_service.py`
- Test: `backend/tests/test_deviations_release_gate.py`

**Routes:** list/create/update/close.

**Tests:**
- Open P1 blocks release.
- Closed P1 allows release.
- P2 warning does not block unless configured.
- Cross-tenant blocked.

### Task P0-E3: Add FE minimal deviation panel

**Objective:** Production/QA can log and close deviations.

**Files:**
- Modify: `frontend/aminra-web/app/supply-chain/batches/page.tsx` or add batch detail page.
- Tests: FE + Playwright.

---

## P0-F — Recall Query MVP

### Task P0-F1: Add affected-batch query service

**Objective:** Given a raw-material lot, list affected batches and release/shipment state.

**Files:**
- Create: `backend/supply_chain/recall_service.py`
- Create: `backend/supply_chain/recall_router.py`
- Test: `backend/tests/test_recall_queries.py`

**Routes:**
- `GET /supply-chain/recall/raw-material-lots/{id}/affected-batches`

**Tests:**
- Raw lot used in 3 batches returns all 3.
- Cross-tenant blocked.
- Unused lot returns empty list.
- Recalled lot marks affected released/shipped batches.

### Task P0-F2: FE recall drill page

**Objective:** QA/admin can run a recall drill.

**Files:**
- Create: `frontend/aminra-web/app/supply-chain/recall/page.tsx`
- Tests: FE + Playwright.

---

# P1 Implementation Plan

## P1-A — SOP Document Control + Immutable Process Version Snapshot

### Task P1-A1: Extend process template metadata

**Files:**
- Create migration: process status/effective/approval columns.
- Modify: `backend/supply_chain/process_router.py`
- Test: `backend/tests/test_process_document_control.py`

**Fields:**
- `process_code`
- `status draft|review|approved|obsolete`
- `effective_from`
- `effective_until`
- `approved_by`
- `approved_at`
- `change_reason`

**Rules:**
- New batch can only use approved/effective process.
- Obsolete process cannot be selected for new batch.

### Task P1-A2: Snapshot process version into batch

**Files:**
- Migration adds `process_snapshot jsonb`, `process_version int`, `process_code` to `production_batches`.
- Modify batch creation.
- Tests.

**Rule:** Later SOP edits must not change historical batch steps/trace.

---

## P1-B — Step Parameters and Criticality

### Task P1-B1: Extend flowchart node schema and batch_steps

**Fields:**
- `criticality`: `normal|control_point|halal_critical|ccp`
- `parameters`: list of `{name, unit, min, max, target, frequency}`
- `evidence_required boolean`
- `role_required`

**Tests:**
- Parameter out of range creates deviation or blocks step approval.
- Evidence required but no photo blocks step approval.
- Critical step needs QA/Halal approval.

### Task P1-B2: FE step execution UI

**Behavior:**
- Render parameter inputs.
- Validate client-side ranges, but backend remains authority.
- Show criticality badges.
- Require evidence upload where configured.

---

## P1-C — Basic Inventory + FEFO

### Task P1-C1: Inventory ledger

**DB:** `inventory_transactions`
- receive, release, consume, adjust, restore, reject, recall_hold.

**Tests:**
- Every qty mutation writes ledger row.
- Available qty equals sum or materialized balance.
- Race condition safe.

### Task P1-C2: FEFO suggestion service

**Rule:** released lots sorted by nearest expiry, then received date.

**Tests:**
- Expiry null sorts after dated lots.
- Expired excluded.
- Insufficient qty suggests split lots if allowed.

---

## P1-D — Finished Goods Lots + Shipment Linkage

### Task P1-D1: Add finished_goods_lots

**Fields:**
- batch_id
- finished_lot_no
- produced_qty
- available_qty
- status `qa_hold|released|shipped|recalled`

### Task P1-D2: Add shipments minimal table

**Fields:**
- shipment_no
- customer_name
- destination_country
- shipped_at
- line items finished_goods_lot_id + qty

**Recall drill:** raw lot → batch → finished goods lot → shipment/customer.

---

## P1-E — E-signature and Audit Trail Hardening

### Task P1-E1: Add electronic signatures table

**DB:** `electronic_signatures`
- tenant_id
- entity_type
- entity_id
- action
- user_id
- user_role
- reason
- payload_hash
- signed_at

**Actions:** raw lot release/reject, step approval, batch QA release, batch seal, deviation close, supplier eligibility update.

### Task P1-E2: FE reason/sign-off modal

**Rule:** Critical actions require explicit reason + confirm identity/session still valid.

---

## P1-F — Reports/Exports/Alerts

### Task P1-F1: Approved Supplier List export

**Output:** CSV/PDF listing only CB-authorized/current NCC, cert number, validity, scope, status.

### Task P1-F2: Expiry alert job

**Use arq, not APScheduler/Celery.**

**Alerts:**
- Supplier eligibility expiring in 60/30/7 days.
- Raw material lot expiring soon.
- Process approval expiring if effective_until used.

### Task P1-F3: Recall drill report export

**Output:** raw lot → affected batches → FG lots → shipments, with status and release/seal evidence.

---

# Test Strategy Matrix

## Database tests

Run for every migration:
- Empty schema upgrade to head.
- Downgrade one step then upgrade.
- Enum constraints.
- FK constraints.
- Unique constraints.
- Index existence for high-query tables.
- Data migration compatibility for existing demo data.

**Commands:**
- `docker compose exec aminra-backend alembic upgrade head`
- `docker compose exec aminra-backend pytest backend/tests/test_migrations_* -v`

## Backend unit tests

Scope:
- Eligibility service.
- Inventory service.
- Batch release validator.
- Recall service.
- Hash/seal snapshot canonicalization.
- Scope-matching helpers.

**Command:**
- `docker compose exec aminra-backend pytest backend/tests/test_*service*.py -v`

## Backend functional/API tests

Scope:
- Raw material lot lifecycle.
- Supplier eligibility routes.
- Batch creation/update/release/seal.
- Deviation lifecycle.
- Recall query.
- Public trace fail-closed.

**Command:**
- `docker compose exec aminra-backend pytest backend/tests/test_supply_chain_* -v`

## Backend integration tests

Scope:
- Real PostgreSQL transaction behavior.
- Tenant isolation.
- Role/permission boundaries.
- File/evidence view boundaries.
- arq alert job wiring.
- Data export includes new objects safely.

**Command:**
- `docker compose exec aminra-backend pytest backend/tests/integration -v`

## Frontend unit/contract tests

Scope:
- API client functions.
- Component states: empty/loading/error/disabled/ineligible.
- Route markers.
- Form validation.
- i18n copy if applicable.

**Commands:**
- `cd frontend/aminra-web && npm test`
- `cd frontend/aminra-web && npm run type-check`
- `cd frontend/aminra-web && npm run build`

## Functional E2E tests

Scope:
- Business user receives raw lot.
- QA releases lot.
- Production creates batch with released lot.
- Step completion with evidence.
- Deviation blocks release.
- Close deviation.
- QA release + seal.
- Public trace works.
- Recall drill returns affected batch.

**Command:**
- `cd frontend/aminra-web && npm run test:e2e -- supply-chain`

## Smoke tests

Local sandbox:
- `docker compose up -d`
- `docker compose ps`
- backend `/health`
- frontend `localhost:3100`
- login flow via Keycloak demo users
- read-only API smoke for supply-chain routes
- public trace released sample lot

**Expected artifact:** `docs/qa/YYYY-MM-DD-aminra-supply-chain-p0p1-smoke/report.md`

## UAT tests

Roles:
- Business owner/admin
- Warehouse receiving
- QA/Halal officer
- Production operator
- Certification Body/provider user
- Anonymous buyer/auditor public trace

UAT journeys:
1. CB authorizes NCC.
2. Business sees eligible NCC only.
3. Warehouse receives raw lot.
4. QA releases raw lot.
5. Production creates batch using raw lot.
6. Operator completes steps/evidence.
7. QA logs deviation and sees release blocked.
8. QA closes deviation.
9. QA releases/seals batch.
10. Buyer scans QR and sees released trace only.
11. QA runs recall drill from raw lot.

Verdict ladder:
- GO: all P0 UAT pass, no P0/P1 defects.
- CONDITIONAL GO: only P2/P3 defects with workaround.
- PARTIAL: tests pass in source but role/browser/runtime evidence incomplete.
- NO-GO: any P0/P1 blocker in eligibility, lot release, batch seal, trace, tenant boundary.

---

# Execution Order

1. P0-A Supplier eligibility.
2. P0-B Raw material lots + incoming QC.
3. P0-C Batch lot consumption.
4. P0-D QA release/seal/public trace gates.
5. P0-E Deviations/CAPA minimal.
6. P0-F Recall query MVP.
7. P1-A SOP document control.
8. P1-B Step parameters.
9. P1-C Inventory ledger + FEFO.
10. P1-D Finished goods + shipments.
11. P1-E E-signature.
12. P1-F Reports/alerts.

Do not start P1 until P0 smoke + UAT P0 are at least CONDITIONAL GO.

---

# Definition of Done per Task

A task is not DONE unless:

1. RED test was written and observed failing for the intended reason.
2. Minimal implementation passes the specific test.
3. Related unit/functional tests pass.
4. Migration upgrade/downgrade passes if DB touched.
5. FE type-check/build/test passes if FE touched.
6. Integration/tenant-boundary test passes if route/query touched.
7. Smoke evidence exists for user-facing flows.
8. Defects are documented with severity.
9. Brain/session note updated after major milestone.
10. No commit/push/deploy unless founder authorizes.

---

# Initial Claude Code Execution Prompt

Use this after founder approval to execute implementation:

```text
You are implementing AMINRA Supply Chain P0/P1 upgrade in /home/user/Documents/aminra-docker-system.

Read first:
- CLAUDE.md
- /home/user/Documents/all-docs/02-Projects/aminra/README.md
- docs/features/supply-chain-p0-p1-implementation-plan.md

Hard rules:
- Strict TDD: write failing test first, run it and show RED, implement minimal code, run GREEN, refactor.
- No commit/push/deploy/delete/secrets unless founder explicitly authorizes.
- Do not modify backend/services/certificate_pdf.py.
- Add new Alembic migrations only; do not edit old merged migrations.
- Every migration needs upgrade and downgrade.
- Every route/query must be tenant-scoped and have negative cross-tenant tests.
- Supplier/NCC Halal eligibility is controlled by CB. AMINRA must not implement internal business-side verification.

Start with P0-A only:
1. Add supplier_eligibilities migration.
2. Add eligibility service.
3. Add eligible supplier route/projection.
4. Add BE tests: DB, unit, functional, integration/tenant boundary.
5. Add FE eligible supplier selection contract and smoke where applicable.

Final report must include:
- Files changed.
- Tests added.
- RED/GREEN evidence commands.
- DB migration verification.
- BE unit/functional/integration results.
- FE type/build/test results if touched.
- Smoke/UAT status: PASS/PARTIAL/BLOCKED.
- Known risks/gaps.
- Commit status: uncommitted unless explicitly authorized.
```
