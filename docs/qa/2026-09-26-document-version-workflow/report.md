# Document approval/version workflow QA report

## Verdict
PASS for scoped source/build/browser evidence. Runtime live deployment is tracked separately in the final QA/deploy report.

## Scope
- Approval date validation: reject `next_review_date` before `effective_date`.
- Supersede validation: the replacement/new document must already be approved.
- Delete safety: deleting a document with child versions returns 409 before any physical file unlink.
- Browser evidence: version-chain modal and supersede action UI through route-mocked Playwright.

## TDD / regression evidence
- Added focused backend regression coverage in `backend/tests/test_document_versioning_integration.py` for:
  - `test_approve_next_review_before_effective_date_422`
  - `test_supersede_requires_new_document_already_approved`
  - `test_delete_document_with_child_returns_409_without_unlinking_file`
- Added browser evidence spec: `frontend/aminra-web/e2e/document-version-workflow-ui.spec.ts`.
- Browser spec was initially red due route matching/test harness drift, then fixed to mock `/official-artifacts` and use exact document-list route matching.

## Commands / results
- Browser route-mock suite:
  - `PW_BASE_URL=http://localhost:3320 npx playwright test e2e/official-artifact-separation-ui.spec.ts e2e/document-version-workflow-ui.spec.ts e2e/document-management-ui-error-evidence.spec.ts --project=desktop-chromium --reporter=line`
  - Result: `6 passed`.
- Container/source focused gate including version workflow tests:
  - `docker compose exec -T aminra-backend sh -lc 'cd /app && PYTHONPATH=/app pytest -q tests/test_official_artifact_separation_contract.py tests/test_official_artifacts_service.py tests/test_document_versioning_integration.py::TestErrorStates::test_approve_next_review_before_effective_date_422 tests/test_document_versioning_integration.py::TestErrorStates::test_supersede_requires_new_document_already_approved tests/test_document_versioning_integration.py::TestErrorStates::test_delete_document_with_child_returns_409_without_unlinking_file'`
  - Result: `7 passed, 3 skipped`.
- Full host `test_document_versioning_integration.py` is not used as final evidence here because host auth fixture errored with `KeyError: access_token`; the container focused lane is the authoritative focused backend evidence.

## Browser evidence
- `docs/qa/2026-09-26-document-version-workflow/screenshots/version-chain.png`
- `docs/qa/2026-09-26-document-version-workflow/screenshots/supersede-action.png`

## Limitations
- Browser evidence uses synthetic route mocks and does not mutate live data.
- Runtime migration/deploy/live health are covered in the final deploy report, not this source/browser report.
