# P0 Traceability Hardening Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Strict TDD: every behavior change starts with a failing test, then minimal implementation, then regression verification.

**Goal:** Close the P0 traceability integrity gaps so AMINRA public QR trace is globally unambiguous, sealed-only, snapshot-backed, and protected from post-seal mutation.

**Architecture:** Introduce an opaque globally unique public trace identifier, require sealed completed batches for public trace, render public trace from immutable sealed snapshot rather than live joins, centralize sealed-batch mutation guards, and enforce seal readiness gates before computing the integrity hash. Avoid cosmetic or partial fixes that only hide symptoms.

**Tech Stack:** FastAPI/asyncpg, PostgreSQL/Alembic, pytest, Next.js frontend trace page, TypeScript/Vitest or source contract tests where available.

---

## Success Criteria

P0 is DONE only when all of these are true and verified by tests:

1. Public QR/trace URL uses a globally unique opaque identifier, not tenant-local `batch_code`.
2. Public trace returns 404 for draft, in-progress, completed-but-unsealed, disabled, or malformed trace IDs.
3. Public trace renders from `sealed_data` snapshot; mutating live supplier/material/certificate/step rows after seal does not change public trace payload.
4. Integrity verification applies to the exact sealed payload exposed publicly.
5. Every mutation route that can change batch trace content rejects sealed batches.
6. Seal is blocked unless required production evidence is complete: steps completed, required approvals present, required checklist/evidence satisfied, and supplier eligibility still valid at seal time.
7. Legacy tenant-scoped `batch_code` remains usable internally, but not as the public trust boundary.
8. Backend focused tests, relevant supply-chain regression tests, migrations, and frontend trace/API contract tests pass.

## Non-Goals

- Do not build full material-lot genealogy/recall graph in this P0. That is P1.
- Do not implement blockchain anchoring in this P0. Keep integrity claim as DB-local sealed hash unless an anchor job already exists.
- Do not redesign public trace UI beyond required field/identifier compatibility.
- Do not weaken supplier eligibility rules to make old fixtures pass.

## Core Design Decisions

### Decision 1: Add `public_trace_id`, not globalize `batch_code`

**Reasoning:** `batch_code` may be business-facing and legally tenant-local. Making it globally unique would force business process changes and still expose guessable identifiers. `public_trace_id` is safer and solves ambiguity directly.

**Schema:**
- `production_batches.public_trace_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid()` or `uuid_generate_v4()` depending existing extension support.
- Optional but recommended: `production_batches.public_trace_enabled BOOLEAN NOT NULL DEFAULT false`.
- Public trace route becomes `/batches/trace/{public_trace_id}`.
- QR URL helper uses `public_trace_id`.

### Decision 2: Public trace is sealed-only

Public trace must require:

```text
status = 'completed'
integrity_hash IS NOT NULL
sealed_data IS NOT NULL
public_trace_enabled = true
```

If `public_trace_enabled` is not added, substitute with `integrity_hash IS NOT NULL` only, but preferred design is explicit publish control.

### Decision 3: Public trace renders immutable sealed snapshot

The public endpoint should not join live `materials`, `suppliers`, `certificates`, or `batch_steps` for the main trace payload. It should:

1. Load batch by `public_trace_id`.
2. Verify sealed hash.
3. Parse `sealed_data`.
4. Return normalized response from sealed snapshot.
5. Optionally append clearly separated `current_warnings` from live data, never mixed into the verified snapshot.

### Decision 4: Seal readiness must be fail-closed

Before seal:

- all steps for template-backed batch must be completed;
- approval-required steps must have `approved_by` and `approved_at`;
- required checklist items must be true/checked;
- required evidence/photo, if specified in template/checklist metadata, must exist;
- all batch materials must still pass supplier eligibility at seal time;
- if any rule cannot be evaluated because legacy data is incomplete, return 400 with clear reason unless migration/backfill marks it as optional.

### Decision 5: Mutation guard must be centralized

Add helper in `backend/supply_chain/batch_router.py` or new module `supply_chain/batch_integrity.py`:

```python
async def assert_batch_mutable(db, batch_id: str, tenant_id: str) -> None:
    row = await db.fetchrow(
        "SELECT integrity_hash FROM production_batches WHERE id=$1 AND tenant_id=$2",
        batch_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(404, "Không tìm thấy lô hàng")
    if row["integrity_hash"]:
        raise HTTPException(403, "Lô hàng đã được seal — không thể thay đổi")
```

Use it in every route that mutates trace-relevant state.

---

## Implementation Tasks

### Task 1: Write RED tests for public trace ID ambiguity

**Objective:** Prove current `batch_code` lookup is unsafe across tenants.

**Files:**
- Modify test: `backend/tests/test_supply_chain_sealing.py` or create `backend/tests/test_supply_chain_public_trace_p0.py`
- Target code: `backend/supply_chain/batch_router.py`

**Steps:**
1. Create two tenants with same `batch_code`.
2. Seal both batches.
3. Call public trace using old `batch_code`.
4. Expected RED: current endpoint returns one arbitrary row instead of requiring an opaque public ID.

**Acceptance:** Test fails against current code for the right reason: public trace is ambiguous.

### Task 2: Add migration for opaque public trace fields

**Objective:** Add globally unique public trace identifier and optional publish flag.

**Files:**
- Create migration: `backend/alembic/versions/040_public_trace_id.py`

**Schema plan:**
- Add `public_trace_id UUID`.
- Backfill existing rows with generated UUIDs.
- Set `NOT NULL`.
- Add unique constraint/index.
- Add `public_trace_enabled BOOLEAN NOT NULL DEFAULT false`.

**Risk controls:**
- Migration must be additive.
- Backfill must not rewrite `batch_code`.
- Downgrade should drop fields/constraint only.

**Tests:**
- migration smoke if project has migration tests;
- source-level assertion if no migration runner available.

### Task 3: Update models/API response to carry `public_trace_id`

**Objective:** Backend returns public trace ID where QR/export needs it without exposing it as editable user input.

**Files:**
- `backend/supply_chain/models.py`
- `backend/supply_chain/batch_router.py`
- relevant tests

**Rules:**
- `BatchCreate` should not accept client-supplied `public_trace_id` unless explicitly justified. Prefer DB default.
- `BatchOut` or detail response can include `public_trace_id` read-only.
- Internal list may include it only if used by QR/export actions.

**Tests:**
- creating batch returns/stores generated public_trace_id;
- client cannot override it if model currently would allow extra fields.

### Task 4: Change QR/export trace URL helper to use public trace ID

**Objective:** QR and PDF point to opaque public trace URL.

**Files:**
- `backend/supply_chain/batch_router.py`
- possibly frontend batch page if it constructs trace URLs

**Rules:**
- `_trace_url()` signature becomes `_trace_url(public_trace_id: str, request: Request | None = None)`.
- QR endpoint must fetch `public_trace_id`, not use `batch_code`.
- Existing displayed `batch_code` remains business label, not route key.

**Tests:**
- QR/PDF response contains `/trace/{public_trace_id}`;
- it does not contain `/trace/{batch_code}` except maybe as displayed label text.

### Task 5: Rewrite public trace endpoint to lookup by `public_trace_id`

**Objective:** Eliminate tenant collision and guessable business-code lookup.

**Files:**
- `backend/supply_chain/batch_router.py`
- tests from Task 1

**Rules:**
- Route may stay `/batches/trace/{trace_id}` but variable name becomes `trace_id`.
- Validate UUID/ULID format.
- Query `WHERE b.public_trace_id = $1`.
- Remove `WHERE b.batch_code = $1` from public path.

**Tests:**
- old batch_code lookup returns 404;
- public_trace_id lookup returns correct row;
- two tenants with same batch_code are independently traceable.

### Task 6: Enforce sealed-only public trace gate

**Objective:** Public trace cannot show unsealed/in-progress/completed-unsealed records.

**Files:**
- `backend/supply_chain/batch_router.py`
- `backend/tests/test_supply_chain_public_trace_p0.py`

**Gate:**

```python
if (
    row["status"] != "completed"
    or not row.get("integrity_hash")
    or not row.get("sealed_data")
    or not row.get("public_trace_enabled")
):
    raise HTTPException(404, "Lô hàng chưa sẵn sàng để truy xuất")
```

**Tests:**
- draft -> 404
- in_progress -> 404
- completed without seal -> 404
- sealed but not public enabled -> 404 if publish flag added
- sealed + public enabled -> 200

### Task 7: Normalize sealed snapshot format

**Objective:** Ensure `sealed_data` contains all fields needed by public trace without live joins.

**Files:**
- `backend/supply_chain/batch_router.py`
- optional helper: `backend/supply_chain/seal_snapshot.py`
- tests

**Snapshot should include:**
- batch: id, batch_code, product_name, status, completed_at, approved_at, approved_by
- company: name and safe public identifiers
- process: name, description/version if needed
- materials: material name, category, quantity/unit, supplier name, supplier eligibility snapshot, certificate number/issuer/validity/scope used at production time
- steps: label, order, status, completed_at, approved_at, performer/approver display, checklist summary, evidence metadata; avoid private file paths
- integrity metadata: hash algorithm, sealed_at, snapshot_version

**Tests:**
- sealed_data has `snapshot_version`;
- all public trace fields can be built from sealed_data alone.

### Task 8: Public trace renders from sealed snapshot only

**Objective:** Prevent live data mutation from changing verified public trace.

**Files:**
- `backend/supply_chain/batch_router.py`
- `backend/tests/test_supply_chain_public_trace_p0.py`

**Steps:**
1. Seal and publish batch.
2. Capture public trace response.
3. Mutate live material/supplier/certificate/step rows directly in DB.
4. Fetch public trace again.
5. Assert verified snapshot fields are unchanged.
6. Assert integrity remains verified.

**Design:**
- Return `verified_snapshot` or same existing shape, but source must be sealed_data.
- If adding `current_warnings`, test it is separate from snapshot and not covered by integrity badge.

### Task 9: Add central sealed mutation guard

**Objective:** One reusable guard prevents missing a route.

**Files:**
- `backend/supply_chain/batch_router.py` or new `backend/supply_chain/batch_integrity.py`
- tests

**Use in routes:**
- update batch
- delete batch
- assign member if assignment changes trace responsibility after seal
- update step
- upload step photo
- approve/reapprove route where applicable
- any material link mutation route if exists

**Tests:**
- after seal, each mutation path returns 403 and does not change DB.
- delete sealed batch returns 403.

### Task 10: Seal readiness validation tests

**Objective:** Force implementation to solve the real approval/evidence completeness problem.

**Files:**
- `backend/tests/test_supply_chain_sealing.py`
- helper fixtures in same file or common fixtures

**RED tests:**
- cannot seal if any step is pending/in_progress/rejected;
- cannot seal if completed step lacks required approval;
- cannot seal if required checklist item is unchecked;
- cannot seal if required evidence/photo is missing when template marks it required;
- cannot seal if material supplier eligibility is now revoked/expired before seal;
- can seal when all readiness conditions are satisfied.

**Important:** Do not weaken rule because existing fixture is incomplete. Update fixture to represent valid production state.

### Task 11: Implement seal readiness validator

**Objective:** Fail-closed validation before hash generation.

**Files:**
- `backend/supply_chain/batch_router.py` or new `backend/supply_chain/seal_readiness.py`

**Suggested helper:**

```python
async def validate_batch_ready_for_seal(db, batch_id: str, tenant_id: str) -> list[str]:
    reasons = []
    # query steps/materials/eligibilities/checklists
    return reasons
```

`approve_batch` must:
- call validator;
- if reasons: `raise HTTPException(400, {"message": "Lô hàng chưa đủ điều kiện seal", "reasons": reasons})`;
- only then build snapshot/hash/update status.

**Tests:**
- All Task 10 tests pass.

### Task 12: Revalidate supplier eligibility at seal time

**Objective:** Prevent batch from being sealed after supplier certificate was revoked/expired post-creation.

**Files:**
- `backend/supply_chain/eligibility_service.py`
- `backend/supply_chain/batch_router.py`
- tests

**Rules:**
- Iterate batch materials.
- Use current supplier/material category to verify eligibility.
- Compare or include current eligibility in seal snapshot.
- If no longer valid, block seal with explicit reason.

**Tests:**
- created while active, revoked before seal -> seal blocked;
- created while active, still active -> seal allowed.

### Task 13: Frontend trace route compatibility

**Objective:** Frontend `/trace/[code]` should treat param as opaque trace ID and not display misleading wording.

**Files:**
- `frontend/aminra-web/app/trace/[code]/page.tsx` or equivalent
- frontend tests/source contracts if present

**Rules:**
- Rename local variable conceptually to `traceId` where practical.
- API call points to `/batches/trace/{traceId}`.
- UI displays `batch_code` from response as business LOT code.
- If 404, show “Trace chưa được công bố hoặc không tồn tại”, not “batch code wrong”.

**Tests:**
- source contract: route param used as trace ID;
- no user-facing copy implying public key is batch code.

### Task 14: Regression scan for remaining public `batch_code` trace assumptions

**Objective:** Catch partial fix.

**Files:**
- backend/frontend source

**Commands:**
- search for `/trace/${batch_code}`
- search for `/batches/trace/{batch_code}`
- search for `WHERE b.batch_code = $1` in public trace context

**Acceptance:**
- Internal batch_code uses remain OK.
- Public URL construction and public lookup no longer use batch_code.

### Task 15: Full verification gate

**Objective:** Prove P0 is solved end-to-end.

**Commands to run in correct environment:**

Backend focused:
```bash
pytest backend/tests/test_supply_chain_public_trace_p0.py -q
pytest backend/tests/test_supply_chain_sealing.py -q
pytest backend/tests/test_supply_chain_batches.py -q
```

Backend regression:
```bash
pytest backend/tests/test_supply_chain_*.py -q
```

Migration:
```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Frontend:
```bash
cd frontend/aminra-web
npm run type-check
npm run lint
npm run build
npm test -- --run
```

Runtime smoke if Docker stack available:
```bash
# create batch -> complete steps -> seal/publish -> fetch /trace/{public_trace_id}
# verify /trace/{batch_code} 404
# mutate live supplier/material -> fetch trace again -> snapshot unchanged
```

**Final report must include:**
- commands run;
- pass/fail evidence;
- unverified gaps;
- migration status;
- whether any commits/pushes were made;
- explicit DONE/PARTIAL/BLOCKED label.

---

## Risk Register

### Risk A: Legacy batches have incomplete step/approval data

**Mitigation:** New strict seal gate applies prospectively. Existing sealed batches remain readable from their snapshot. If old sealed_data is missing fields, public trace adapter supports `snapshot_version` fallback without joining live mutable data.

### Risk B: Frontend or PDF still uses batch_code public URL

**Mitigation:** Regression scan and tests assert no public trace URL construction from `batch_code`.

### Risk C: Hash changes due to JSON serialization differences

**Mitigation:** Canonical serialization: `json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)`. Use same helper for sealing and verifying.

### Risk D: Publish flag creates blocked UX because nobody sets it

**Mitigation:** Decide policy explicitly:
- Option 1: `approve_batch` automatically sets `public_trace_enabled = true`.
- Option 2: separate “Publish trace” endpoint after approval.

Preferred for control: Option 2, but for current demo velocity Option 1 is acceptable if labeled.

### Risk E: Tests fail because old fixtures assumed permissive behavior

**Mitigation:** Treat as fixture migration, not production rule weakening. Update fixtures to create valid completed/approved/evidence-ready batches.

---

## Recommended Execution Order

1. Public trace ID migration + model plumbing.
2. Public trace lookup/gate tests and implementation.
3. Sealed snapshot normalization and rendering.
4. Mutation guard coverage.
5. Seal readiness gate.
6. Frontend/API compatibility.
7. Full regression and runtime smoke.

Do not start broad UI polish or P1 recall graph until these P0 invariants are closed.
