# AMINRA Document Management QA Review — 2026-09-17

## Verdict

**NO-GO for document-management create/upload path.** Existing list/detail authorization looks broadly tenant-scoped and focused automated tests pass, but live runtime smoke found a **P0 functional regression**: a business user can list existing documents, but cannot upload a new document because `/api/documents/upload` inserts `documents.user_id = user["sub"]` where `user["sub"]` is the Keycloak subject, not the AMINRA `users.id`. PostgreSQL rejects the insert with `documents_user_id_fkey`, returning HTTP 500.

This is the same class as prior Keycloak-sub-vs-AMINRA-id FK regressions and must be fixed before customer/pilot usage of document upload.

## Scope

Reviewed document-management group covering:

- Business document library: list/detail/revisions/promote/preview/download/upload/evaluate/delete/dashboard stats.
- Document approval/versioning: submit/approve/reject/supersede/versions/status.
- Dossier CRUD and document linkage.
- Submission document workflow: submit, received docs, revision requests/resubmit, replace doc, finalize, provider/auditor status actions.
- PDF/render registry and file preview/download security-relevant paths.
- Frontend document/dossier/submission pages and helper library.

Out of scope for this pass:

- Full browser E2E matrix.
- AI evaluation correctness and LLM scoring quality.
- Production SMTP/customer onboarding.
- Fix implementation. This report is assessment evidence only.

## Success Criteria

P0 acceptance criteria for this group:

1. Business user can list, upload, view detail, download/preview, and delete own tenant documents without 500.
2. Provider/auditor cannot access arbitrary business document library; provider access is limited to submitted documents.
3. Anonymous access is denied for protected document APIs.
4. File upload enforces extension, MIME, size, zip-bomb protections, tenant-scoped storage, and path traversal defense.
5. Dossier CRUD is tenant-scoped and writes canonical AMINRA user IDs, not Keycloak subjects.
6. Focused backend/FE tests and static gates pass.
7. Runtime smoke leaves no QA residue.

## Evidence Directory

- QA folder: `docs/qa/20260917-134349-document-management-review/`
- Raw evidence:
  - `evidence/raw/route-inventory.md`
  - `evidence/raw/db-schema-inventory.txt`
  - `evidence/raw/static-scan.txt`
  - `evidence/raw/backend-focused-tests.txt`
  - `evidence/raw/frontend-focused-gates.txt`
  - `evidence/raw/frontend-focused-vitest.txt`
  - `evidence/raw/runtime-api-smoke.txt`
  - `evidence/raw/runtime-upload-500-logs.txt`
  - `evidence/raw/runtime-upload-orphan-cleanup.txt`
  - `evidence/raw/generic-gates.txt`

## Analysis

### Backend API Inventory

Primary routes found:

- `backend/auth/document_router.py`
  - `GET /api/documents`
  - `GET /api/documents/revisions/{doc_type_id}`
  - `POST /api/documents/{doc_id}/promote`
  - `GET /api/documents/{doc_id}`
  - `GET /api/documents/{doc_id}/preview`
  - `GET /api/documents/{doc_id}/file`
  - `POST /api/documents/upload`
  - `POST /api/documents/{doc_id}/evaluate`
  - `DELETE /api/documents/{doc_id}`
  - `GET /api/dashboard/stats`
  - document approval/versioning endpoints.
- `backend/auth/dossier_router.py`
  - `GET /dossiers`
  - `POST /dossiers`
  - `GET /dossiers/{dossier_id}`
  - `PATCH /dossiers/{dossier_id}`
  - `DELETE /dossiers/{dossier_id}`
- `backend/auth/submission_router.py`
  - submit/received/documents/revision/replace/finalize/approve flows.
- `backend/auth/pdf_render_router.py`
  - `GET /render-pdf/health`
  - `GET /render-pdf/registry`
  - render endpoints not fully enumerated by the decorator parser due decorator formatting, but file was included in static/compile gates.

### Data Model Inventory

Current live DB schema confirms relevant tables:

- `documents`
  - tenant-scoped: `tenant_id UUID NOT NULL`
  - ownership: `user_id UUID REFERENCES users(id)`
  - file metadata: `filename`, `original_filename`, `file_path`, `file_size`, `mime_type`
  - workflow/versioning: `status`, `approval_status`, `version_number`, `version_parent_id`, `approver_id`, `approved_at`, `effective_date`, `retention_*`, `superseded_by_id`, `dossier_id`
- `dossiers`
  - `tenant_id`, `standard_type_id`, `title`, `status`, `notes`, `created_by`
- `submissions`
  - `business_tenant`, `provider_id`, `auditor_id`, `document_ids UUID[]`, `revision_*`, `deadline`, `archived_at`
- `standard_types`
  - standard catalogue used by dossiers.

### Positive Findings

- Tenant filtering is consistently visible in core document read/detail paths: `WHERE d.tenant_id = $2` for document detail and `WHERE d.tenant_id = $1` for list.
- Provider preview/download access has an explicit submission-membership check rather than whole-tenant access; comments note a prior C6 leak fix.
- Upload validation exists in `auth/upload_utils.py`:
  - extension allowlist,
  - magic MIME detection,
  - max file size,
  - zip-bomb checks for DOCX/PPTX/ODT,
  - path traversal defense on saved file path.
- Dossier create resolves DB user by email for `created_by`, avoiding the exact Keycloak-sub FK issue there.
- Focused backend test set passed: **157 passed, 200 skipped**.
- Focused frontend Vitest passed: **24 passed**.
- TypeScript `tsc --noEmit`, ESLint, Python compile, `git diff --check`, backend health, frontend health all passed.

## Defects / Risks

### P0 — Document upload 500 due Keycloak subject stored as `documents.user_id`

- Evidence:
  - Runtime smoke: `business_upload_status=500`
  - Backend log: `ForeignKeyViolationError: insert or update on table "documents" violates foreign key constraint "documents_user_id_fkey"`
  - Failed key shape: `documents.user_id = <Keycloak sub>` not present in `users.id`.
- Code evidence:
  - `backend/auth/document_router.py:618-630` inserts `user["sub"]` into `documents.user_id`.
- Impact:
  - Business users cannot upload new documents through the currently deployed local stack.
  - File is written before DB insert; failed insert leaves an orphan physical file. The QA orphan file from this smoke was deleted and logged in `runtime-upload-orphan-cleanup.txt`.
- Required fix:
  - Resolve canonical AMINRA user ID via `auth.identity.resolve_canonical_user_id(user, db)` before insert.
  - Wrap physical write + DB insert in compensating cleanup: if DB insert fails, unlink the saved file.
  - Add live-token regression test for upload using a real Keycloak business token.

### P1 — Frontend document delete can false-refresh after failed DELETE

- Evidence:
  - Static scan flags `frontend/aminra-web/app/documents/page.tsx:351`: `await fetch(... DELETE ...)` then `fetchDocs(page)` without checking `res.ok`.
- Impact:
  - User may see a refreshed list and assume deletion succeeded even if backend returns 403/404/500.
- Required fix:
  - Use shared `apiFetch`/`apiJson` error handling or check `res.ok` and surface `detail`.

### P1 — Dossier audit metadata is manually interpolated JSON

- Evidence:
  - `backend/auth/dossier_router.py:212-217` builds JSON string using `f'{{"title":"{req.title}",...}}'`.
- Impact:
  - A title containing quotes/control characters can break JSON cast and turn dossier creation into a server error after row insert attempt path.
- Required fix:
  - Use `json.dumps(..., ensure_ascii=False)` and pass to `$4::jsonb`, or use asyncpg JSON adapter if available.

### P2 — Many document-versioning tests are skipped

- Evidence:
  - `tests/test_document_versioning_sec.py`, `func.py`, `integration.py`, `regression.py` largely skipped; aggregate focused backend result: **157 passed, 200 skipped**.
- Impact:
  - Existing test count overstates executable confidence for versioning workflows.
- Required fix:
  - Triage skip reasons and convert P0/P1 authorization/versioning tests into executable suite.

### P2 — Dynamic SQL patterns require continued guardrails

- Evidence:
  - `document_router.py` builds SQL fragments for filter clauses using fixed field names and parameter placeholders.
  - `dossier_router.py` builds update `SET` clauses from Pydantic model fields.
- Assessment:
  - No immediate injection found because user values are parameterized and field names come from fixed model fields, but this pattern should stay under test/guardrail review.

## Tests

### Passed

- Backend focused tests:
  - Command: `docker compose exec -T aminra-backend python -m pytest ... --tb=short -q`
  - Result: **157 passed, 200 skipped in 4.92s**
- Frontend focused Vitest:
  - `revision-panel.test.tsx`, `submit-application.test.tsx`
  - Result: **24 passed**
- Frontend gates:
  - `tsc --noEmit`: PASS
  - `npm run lint -- --max-warnings=999999`: PASS
- Generic gates:
  - `git diff --check`: PASS
  - `python -m py_compile auth/document_router.py auth/dossier_router.py auth/pdf_render_router.py services/document_versioning.py`: PASS
  - Backend health: `status=ok`, DB connected, Qdrant connected
  - Frontend health proxy: `status=ok`

### Runtime Smoke

Executed safe local API smoke with real Keycloak tokens. Results:

- `/health`: `200`
- Anonymous `GET /api/documents`: `401` PASS
- Provider `GET /api/documents`: `403` PASS
- Business `GET /api/documents`: `200` PASS; response shape OK
- Business `POST /api/documents/upload`: `500` FAIL

Because upload failed at create, downstream live smoke for newly-created detail/file/delete could not proceed. Existing detail/provider boundary was not tested against the newly created doc because no doc could be created.

## Solution / Recommended Fix Plan

P0 first:

1. Patch `upload_document` to call `resolve_canonical_user_id(user, db)` and insert that into `documents.user_id`.
2. Add cleanup-on-failure around file write/DB insert:
   - write file,
   - attempt insert,
   - on DB exception, unlink saved file and raise structured 500/422 without leaking DB internals.
3. Add regression tests:
   - unit/mock: Keycloak `sub` differs from DB `users.id`; insert uses canonical ID.
   - live-token smoke: business token uploads `.txt`, returns 200, DB row `user_id` exists in `users`, file exists, delete removes both DB row and file.
   - failure cleanup: simulated DB insert failure removes physical file.
4. Re-run focused gates and runtime smoke.
5. Only after P0 green, expand runtime smoke to preview/download/delete and provider-submission-scoped access.

## Risks

- **Customer workflow blocker:** Business users cannot add required compliance documents; onboarding stalls.
- **Data hygiene risk:** failed uploads can leave orphan files on disk.
- **Recurring class risk:** Any route using `user["sub"]` for AMINRA FK writes is suspect post-Keycloak migration.
- **False-success UX risk:** frontend raw fetch patterns can hide failed writes.
- **Coverage risk:** skipped document-versioning security tests reduce confidence in approval/versioning edge cases.

## Improvements

- Add a pre-commit/static guard for new `user["sub"]` usages in SQL `INSERT/UPDATE` FK contexts unless annotated with a justified exception.
- Centralize document ownership writes through a helper, e.g. `resolve_document_actor_id(user, db)`.
- Add a small API-smoke script under `scripts/qa/` for document lifecycle; keep tokens read from `.qa` and never printed.
- Convert critical skipped document-versioning tests into executable tests before any pilot/customer demo involving document approval.
- Refactor frontend document write actions to shared `apiFetch`/`apiJson` to prevent false success.

## Final Status

- Review artifacts created: yes.
- P0 blocker found: yes.
- Code changed: no, assessment only.
- QA residue cleanup: yes, failed-upload orphan file removed.
- Recommended next action: fix P0 upload canonical-user regression before any customer-facing document-management handoff.
