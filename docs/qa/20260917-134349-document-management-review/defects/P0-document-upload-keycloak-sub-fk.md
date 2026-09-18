# P0 — Document upload fails with Keycloak-sub FK violation

## Summary

Business document upload returns HTTP 500 because `backend/auth/document_router.py::upload_document` inserts `user["sub"]` into `documents.user_id`, but after Keycloak migration `user["sub"]` is the Keycloak subject, not the AMINRA `users.id` referenced by `documents_user_id_fkey`.

## Evidence

- Runtime smoke output: `business_upload_status=500`
- Backend log: `ForeignKeyViolationError: insert or update on table "documents" violates foreign key constraint "documents_user_id_fkey"`
- Code site: `backend/auth/document_router.py:618-630`
- Report: `docs/qa/20260917-134349-document-management-review/report.md`

## Impact

- Business users cannot upload new compliance documents.
- The physical file is written before the DB insert; failed insert leaves orphan files unless cleaned up.

## Expected Behavior

- Upload returns 200/201 with a new document ID.
- DB `documents.user_id` references canonical AMINRA `users.id`.
- Failed insert cleans up the saved file.

## Recommended Fix

1. Use `auth.identity.resolve_canonical_user_id(user, db)` in `upload_document`.
2. Insert the canonical DB ID into `documents.user_id`.
3. Add compensating file cleanup on DB insert failure.
4. Add live-token regression smoke for business upload/delete.
