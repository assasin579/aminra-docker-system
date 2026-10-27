# AMINRA J1/J2 task graph — current execution

Canonical state: `J1_J2_CHECKPOINT.md`; acceptance evidence: `J1_J2_ACCEPTANCE_MATRIX.md`; result summary: `J1_J2_EXECUTION_RESULT.md`.

## Authority and boundary

- Owner-authorized scope is the isolated workspace `/home/user/.cache/aminra-dashboard-integrated`, branch `dashboard/execution-2026-10-26`, exact base `4d1ae677598301e62ff6b06208d5c5832c7290f9`.
- Local synthetic browser and disposable DB are allowed. No original checkout writes, shared/runtime DB, push, merge, deploy, production browser/UAT, or customer pilot. STOP C and customer-pilot NO-GO remain.
- Acceptance must be lane-specific: source/unit, app-role disposable DB, API-mocked browser, integrated browser, RLS, release/pilot. A PASS in one lane does not promote another.

## Tasks

| ID | Status | Dependency | Current result / remaining acceptance |
|---|---|---|---|
| T00 Authority/baseline | DONE | — | Exact isolated branch/base verified; original checkout untouched. Dirty workspace includes unidentified files; stage only reviewed paths. |
| T01 J1/J2 state + retry semantics | PARTIAL | T00 | Resubmit and revision-request idempotency slices have app-role DB evidence; latest relevant DB+route suite 24 passed. Still need J1 submit retry/stale/concurrent cases and full route-level resource serialization. Do not generalize partial retry coverage. |
| T02 Historical download authorization/version | PARTIAL | T00 | Historical round file passed through real FileResponse with exact synthetic bytes/hash; unrelated same-tenant doc denied. Other actor/assignment/current-revocation and exact route variants remain not fully tested. |
| T03 Download event semantics | NOT TESTED | T02 | Distinguish URL issuance, response status, and fully streamed bytes. No claim of completed byte-served event/logging. |
| T04 Integrated local browser journey | PARTIAL (J1-A02 subacceptance now PASS) | T01–T03 | The latest rendered journey verifies exact Dossier/pinned requirements version/slot/document version through the readback API and DB join; reuse/wrong-tenant app-role DB cases pass. Broader J1/J2 workflow and logging/access gaps remain per matrix; do not generalize this subacceptance. |
| T05 G1 browser/component regressions | PASS (separate evidence lane) | T00 | G1 API-mocked Playwright 2/2; component/SW Vitest 9/9. Not backend E2E or installed service-worker/runtime proof. |
| T06 Scoped handoff and lifecycle | IN_PROGRESS | T01–T05 | Diff review, exact-baseline patch or scoped local commit, final diff check, artifact/hash refresh and task-resource cleanup still to complete. |

## Findings that constrain implementation

- `request_id` is not a durable retry receipt; request-revision and resubmit have a narrower idempotency implementation using the existing replay helper. Remaining J1 submit/stale/concurrency acceptance still needs proof.
- D-B permits reuse-by-reference across Dossiers. Do not satisfy upload attach by blindly relying on a single-Dossier `documents.dossier_id` FK. Any association must preserve tenant ownership, bind to the Dossier's pinned requirements version, and fail closed on a mismatched document type/slot.
- Current Documents UI ignores a `?dossier=` query and sends only file + doc_type to upload. Backend upload returns 200 but creates a standalone document. DB-only fixture attachment is not UI/application-path acceptance.
- Historical file route evidence is synthetic and app-role scoped; it does not prove OIDC, RLS, full access matrix, or event logging.
- Current DB role was non-superuser/no-BYPASSRLS; public RLS policy count was 0. RLS is NOT TESTED.

## Resume order

1. Complete source diff review, matrix/checkpoint/result/index consistency, exact counts and final diff/type/lint checks.
2. Create scoped local commit or generate a patch from this exact baseline and forward-apply-check it. Exclude unrelated WIP.
3. Clean the verified task-owned API/DB/network/env/Next resources and confirm absence.
4. Preserve J1-A02 and any other unproved acceptance as PARTIAL/FAIL; do not claim J1/J2 DONE or change STOP C/customer-pilot NO-GO.