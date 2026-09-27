# AMINRA — Document Approval/Versioning + Official Artifact Runtime QA

Date: 2026-09-26
Scope: local sandbox runtime validation for document approval/versioning hardening and immutable official artifact separation.
Verdict: LOCAL/SANDBOX RUNTIME PASS for covered lanes. Production/customer GO remains PARTIAL.

## Executive verdict

PASS for the requested local sandbox scope:

- Source/build gates passed.
- Alembic migrated from `050_complaints_appeals` to `051_official_artifacts (head)`.
- Backend and frontend app services were rebuilt/recreated and are healthy.
- `OFFICIAL_ARTIFACTS_DIR=/app/official_artifacts` is mounted on a separate Docker volume (`official-artifacts-data`).
- Browser route-mocked evidence proves read-only official-artifact UI separation plus document version/error-state flows.
- Runtime image focused backend tests passed for covered official-artifact service/contract behavior.

Not a production/customer-pilot GO:

- Browser evidence is route-mocked, not full credentialed live approval flow.
- Full live API/UAT for real approval -> artifact creation -> list/download -> delete-block remains a separate stronger gate.
- Existing broader AMINRA blockers still apply: SMTP/customer onboarding, edge/CDN SLO, dependency/security backlog, mobile/cross-browser matrix, broader role workflow UAT.

## Environment

- Repo: `/home/user/Documents/aminra-docker-system`
- Branch: `feat/cb-trust-core-rbac-decisions`
- Runtime: local Docker Compose sandbox
- Backend URL: `http://localhost:8100`
- Frontend URL: `http://localhost:3100`
- Migration head after apply: `051_official_artifacts (head)`

## Implementation summary

Backend:

- Added Alembic migration `backend/alembic/versions/051_official_artifacts.py`.
- Added official artifact service `backend/services/official_artifacts.py`.
- Updated `backend/auth/document_router.py` to create/list/download official artifacts and block unsafe deletes.
- Added official-artifact service/contract tests.
- Extended document-versioning integration coverage for approval date, supersede, and blocked delete paths.

Frontend:

- Added separate `Bản chính thức` tab on `/documents`.
- Official artifacts render as read-only records with download only.
- Source/customer documents remain separate from immutable official artifacts.
- Version chain and supersede UI evidence added.
- Error-state browser evidence added for list/detail/delete/upload API failures.

Runtime/Docker:

- Added `OFFICIAL_ARTIFACTS_DIR=/app/official_artifacts` to backend service.
- Added `official-artifacts-data:/app/official_artifacts` volume mount.
- Declared `official-artifacts-data` named volume.

## Evidence index

Terminal evidence:

- `evidence/terminal/db-backup-paths.txt`
- `evidence/terminal/db-backup-sha256.txt`
- `evidence/terminal/migration-upgrade.txt`
- `evidence/terminal/migration-current.txt`
- `evidence/terminal/official-artifacts-db-check.txt`
- `evidence/terminal/docker-build-app-services.txt`
- `evidence/terminal/docker-up-app-services.txt`
- `evidence/terminal/official-artifacts-env-volume.txt`
- `evidence/terminal/runtime-backend-focused-tests-final.txt`
- `evidence/terminal/runtime-frontend-playwright-route-mock-final.txt`
- `evidence/terminal/compose-ps-final.txt`
- `evidence/terminal/backend-health-final.json`
- `evidence/terminal/frontend-documents-head-final.txt`

Screenshots:

- `../2026-09-26-official-artifact-separation/screenshots/official-artifacts-read-only.png`
- `../2026-09-26-document-version-workflow/screenshots/version-chain.png`
- `../2026-09-26-document-management-ui-error/screenshots/list-error.png`
- `../2026-09-26-document-management-ui-error/screenshots/detail-error.png`
- `../2026-09-26-document-management-ui-error/screenshots/delete-error.png`
- `../2026-09-26-document-management-ui-error/screenshots/upload-error.png`

Backups:

- DB backup: `backups/aminra-pre-official-artifacts-20260926-124500.dump`
- Schema backup: `backups/aminra-pre-official-artifacts-20260926-124500-schema.sql`
- SHA256 hashes recorded in `evidence/terminal/db-backup-sha256.txt`.

## Verification matrix

| Lane | Result | Evidence |
|---|---:|---|
| DB backup before migration | PASS | `db-backup-paths.txt`, `db-backup-sha256.txt` |
| Alembic migration apply | PASS | `migration-upgrade.txt` |
| Migration current/head | PASS | `migration-current.txt`, `migration-current-after-deploy.txt` |
| DB table/trigger check | PASS | `official-artifacts-db-check.txt` |
| Backend/frontend rebuild/recreate | PASS | `docker-build-app-services.txt`, `docker-up-app-services.txt` |
| Official artifact env/volume | PASS | `official-artifacts-env-volume.txt` |
| Runtime backend focused tests | PASS | `6 passed, 4 skipped` in `runtime-backend-focused-tests-final.txt` |
| Runtime frontend Playwright route-mock | PASS | `6 passed` in `runtime-frontend-playwright-route-mock-final.txt` |
| Runtime health | PASS | `compose-ps-final.txt`, `backend-health-final.json`, `frontend-documents-head-final.txt` |
| Source/backend focused host tests | PASS | captured in session terminal; `7 passed` |
| Frontend lint/build | PASS | captured in session terminal |

## Known limitations

- Runtime backend test lane has 4 expected skips because some integration tests are environment/fixture dependent or frontend-source-only in the backend image.
- Browser tests use route mocks to prove UI contracts; they do not prove a live authenticated approval workflow creates an artifact end-to-end.
- Official artifact retention/legal-hold policy is represented in metadata but not a complete operator workflow yet.
- Sentry deprecation warnings appeared during frontend build and remain tech debt.

## Follow-up recommendations

P0/P1:

1. Add credentialed live API/UAT: approve document -> official artifact row/file created -> list/download works -> source document delete returns 409.
2. Add runtime log/metric alert for approval failure if official artifact creation fails.
3. Add operator/admin retention/legal-hold workflow before production reliance.

P2:

1. Fix Sentry deprecation warnings.
2. Normalize Playwright test tokens to avoid `Invalid token format` alert noise in screenshots.
3. Address pytest cache permission warning on host.

## Final verdict

LOCAL/SANDBOX RUNTIME PASS for covered official artifact separation, versioning guardrails, read-only UI separation, and runtime migration/deploy evidence.

Production/customer-pilot remains PARTIAL until full credentialed live approval workflow, broader role/browser coverage, SMTP/customer onboarding, edge/CDN SLO, and dependency/security backlog are closed.
