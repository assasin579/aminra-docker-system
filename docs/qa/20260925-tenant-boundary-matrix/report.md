# AMINRA Document Management — Tenant Boundary Matrix

Date: 2026-09-25
Repo: `/home/user/Documents/aminra-docker-system`
Branch: `feat/cb-trust-core-rbac-decisions`
Verdict: **PASS for source/container-tested document-management tenant boundary matrix; PARTIAL for deployed/runtime readiness**

## Scope / acceptance criteria

Covered P0 object-boundary invariants:

- Business actor can list/detail/file/preview/evaluate/promote/delete only documents scoped to its canonical AMINRA tenant.
- Cross-tenant business access returns `404` for object lookups/mutations without leaking existence and without mutation.
- Provider/auditor document file/preview access is submission-bound via `submissions.document_ids`; role alone and business tenant membership are insufficient.
- Delete cannot unlink arbitrary host paths even if a document metadata row is corrupt/hostile; physical delete is constrained to configured `UPLOAD_DIR`.
- Existing upload hardening remains green: canonical AMINRA `users.id` ownership and DB-failure file cleanup.

## Matrix evidence

- Matrix: `docs/qa/20260925-tenant-boundary-matrix/tenant-boundary-matrix.tsv`
- Status: `docs/qa/20260925-tenant-boundary-matrix/status.tsv`
- Baseline live API UAT rerun: `docs/qa/20260925-202249-document-management-live-uat/report.md`

## RED → GREEN evidence

Initial tenant-boundary test run after adding the matrix:

- `12 passed / 1 failed`
- Failing invariant: `DELETE /documents/{id}` would unlink `documents.file_path` directly without checking it stayed under `UPLOAD_DIR`.
- Risk class: arbitrary file delete if a document row is corrupted/hostile even after tenant SQL matches.

Patch applied:

- `backend/auth/document_router.py::delete_document` now resolves both `UPLOAD_DIR` and row `file_path`, refuses paths outside upload root, returns controlled `500`, preserves the metadata row, and does not unlink the external file.

Final focused gate:

```bash
docker compose exec -T aminra-backend pytest \
  tests/test_document_tenant_boundary_matrix.py \
  tests/test_document_upload_hardening.py \
  tests/test_canonical_identity_usage_contract.py \
  -q
```

Result:

- `17 passed in 2.73s`

Live credentialed API baseline rerun:

```bash
scripts/qa/run-document-management-live-uat.sh
```

Result:

- PASS, report: `docs/qa/20260925-202249-document-management-live-uat/report.md`
- Covered baseline: anonymous list blocked, provider upload forbidden, business upload/list/detail/file/delete succeeds.

Static hygiene:

```bash
git diff --check
```

Result: PASS.

## Boundaries / non-claims

- This is **not yet a backend image rebuild/restart/deploy**. Source was patched and copied into the running backend test container for pytest verification; the running service should be rebuilt/recreated before claiming runtime deploy readiness.
- This is **not full browser UI UAT**. UI error states and cross-tenant browser flows remain separate gates.
- This is **not full approval/version workflow certification**. Draft/submitted/approved/rejected immutability and official-artifact separation remain open.
- This is **not production/customer-pilot GO**.

## Current score impact

- Before this slice: document-management overall remained PARTIAL, with tenant/object-boundary coverage still a major gap.
- After this slice: source-level tenant boundary confidence for the covered API object paths is materially improved.
- Overall document-management readiness is still **PARTIAL** because deployment, browser UI, approval/version lifecycle, official artifact model, and production gates are not closed.
