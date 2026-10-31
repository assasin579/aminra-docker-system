# Document domain contracts

## Responsibilities and public compatibility

| Surface | Purpose | Backend | Browser proxy |
|---|---|---|---|
| Kho tài liệu | Tenant library of reusable source files | `/api/documents` | `/api/api/documents` |
| Hồ sơ chứng nhận | Preparation against pinned published requirement slots | `/dossiers` | `/api/dossiers` |
| Hồ sơ đã gửi / nhận | Evidence explicitly shared with the selected CB and its historical rounds | `/api/submissions` | `/api/api/submissions` |
| AI analysis | Analysis plus an explicit, independent library-save outcome | `/evaluate` | `/api/evaluate`; legacy `/api/upload` retained |
| Internal approval | Approval state machine and immutable official artifacts | `/api/documents/{id}/…` | `/api/api/documents/{id}/…` |

The double `/api` is the existing browser-to-backend proxy mapping. URLs remain compatible. A route name alone does not establish a second document store.

## File identity, history and authority

- Library callers use `GET /api/documents?view=all`. Pagination and filters still apply. Independent files with the same `doc_type` stay separate. The legacy default `view=latest_by_type` remains available for existing callers.
- `GET /api/documents/revisions/{type}` lists uploads of a classification within the business tenant. It is not a version family. The UI calls it “Các lần tải lên cùng loại”; its ordinal is not a formal version number.
- A version family follows existing `version_parent_id` links. `POST /api/documents/{id}/promote` requires `can_edit` and sets a separate current pointer for that family. It never changes `uploaded_at`, approval state or submitted evidence. Repeating the same selection preserves `selected_at` and adds no duplicate selection audit.
- Formal supersede remains owner/IHC controlled and reconciles existing selections when an approved replacement joins the chain. An obsolete version cannot be selected again. Referenced documents remain protected by existing foreign keys and attachment/version guards.
- Internal approval, AI compliance and a CB decision are distinct. Additive `ai_score` and `cb_score` expose the score provenance; the legacy `compliance_score` remains compatible. Missing historical AI scores are not reconstructed from a potentially CB-overwritten score.
- A provider's per-type submission history includes only that submission's current document IDs and immutable `submission_revision_requests.submitted_document_ids` snapshots. Business actors can still access their own library. Tenant membership alone does not share a file with a CB.

## Canonical ingestion

Both `/dossiers/{id}/documents` and the legacy `/api/documents/upload` with `dossier_id` delegate to `services.document_ingestion.attach_dossier_document`. They enforce published pinned slots, canonical actor/tenant identity and create the same immutable attachment association. The canonical route requires `Idempotency-Key`; legacy upload accepts it additively and generates a request key when absent for compatibility. A client wanting retry deduplication must retain its key.

Standalone uploads and AI persistence use `save_library_document`; a failed DB transaction removes the newly written file. Attaching an existing document still reuses its immutable source identity. Uploading a library file alone does not attach or submit it to a dossier.

Business AI ingestion and reevaluation require `can_upload`. `/evaluate` returns `document_save_status` (`saved`, `failed`, `not_applicable`), `document_id` when saved, and a safe `document_save_error` when AI succeeds but persistence fails. Provider analysis remains analysis only. A client must not infer persistence from HTTP 200 or an AI score. The legacy upload proxy preserves language and previous context.

## Migration and release

Migration `057_document_current_versions` follows `056_j1j2_lineage_merge` and only adds the current-selection table, tenant/lineage validation and app-role grants. It does not backfill approvals, rewrite timestamps, merge files, or migrate existing attachments. The runtime role remains `aminra_app`; schema changes run as the migration owner.

Before rollout: review the exact source diff, verify the live head is 056, take and verify a backup, apply 057 through the controlled migration path, then deploy the verified backend/frontend images and smoke-test the mapped routes. Keep previous application images available. Older application code can coexist with the additive table; once selection rows exist, downgrade refuses to drop them. Recover forward rather than deleting selections or restoring a stale backup over newer evidence.

Source merge and production release are separate operations under `docs/operations/git-workflow.md`. This document does not authorize deployment or assert that a particular image is serving.

## Acceptance

Maintained tests cover read-only selection/AI denial before mutation, explicit AI save outcomes, same-type files across two dossiers, current-selection idempotency and stable chronology, cross-tenant/wrong-chain rejection, current and historical CB metadata scope, canonical legacy upload attachment/retry, failed-file cleanup and selection reconciliation after formal supersede. PostgreSQL tests require an explicit disposable database and a non-superuser application role. Never point the acceptance suite at production.

The retired `DossierDocumentUpload` component had no production imports; its legacy-only tests were replaced by actual-page UI tests and real PostgreSQL ingestion acceptance. Published API compatibility endpoints remain available.
