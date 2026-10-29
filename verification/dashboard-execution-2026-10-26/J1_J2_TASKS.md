# AMINRA J1/J2 task graph — current execution

Canonical state: `J1_J2_CHECKPOINT.md`; acceptance evidence: `J1_J2_ACCEPTANCE_MATRIX.md`; result summary: `J1_J2_EXECUTION_RESULT.md`.

## Authority and boundary

- Owner-authorized scope is the isolated workspace `/home/user/.cache/aminra-dashboard-integrated`, branch `dashboard/execution-2026-10-26`, verified source/test baseline `d4b7601864ff0014ae5cba950c421e43f783b813`.
- Local synthetic browser and disposable DB are allowed. No original checkout writes, shared/runtime DB, push, merge, deploy, production browser/UAT, or customer pilot. STOP C and customer-pilot NO-GO remain.
- Acceptance must be lane-specific: source/unit, app-role disposable DB, API-mocked browser, integrated browser, RLS, release/pilot. A PASS in one lane does not promote another.

## Tasks

| ID | Status | Dependency | Current result / remaining acceptance |
|---|---|---|---|
| T00 Authority/baseline | DONE | — | Exact isolated branch/base verified; original checkout untouched. Dirty workspace includes unidentified files; stage only reviewed paths. |
| T01 J1/J2 state + retry semantics | DONE (local synthetic) | T00 | Current app-role DB suite plus focused replay tests cover same-key replay, changed-payload conflict, concurrent same/different keys, stale state, atomic rollback and current permission recheck; scoped synthetic actor/resource matrix only. See matrix J1-A05/J2-A05 raw evidence. |
| T02 Historical download authorization/version | DONE (app-role synthetic) | T00 | Exact historical bytes/hash, assigned/current scope, wrong-scope/unassigned/revoked denial and immutable snapshot membership are covered by the named app-role tests; auth enrichment remains synthetic. |
| T03 Download event semantics | DONE (server lifecycle semantics) | T02 | Tests distinguish authorized-before-response, response-started, body-complete, interrupted and URL-issued=0; ASGI send completion is not client receipt. |
| T04 Integrated local browser journey | DONE (full-stack synthetic) | T01–T03 | Rendered Business/CB workflow traverses Next proxy, backend, disposable PostgreSQL/storage; exact persisted Dossier/version/slot, revision/resubmit/diff and historical file bytes/hash verified. Auth remains synthetic; setup/supporting observations include page-side fetch, so not live OIDC/UAT. |
| T05 G1 browser/component regressions | PASS (separate evidence lane) | T00 | G1 API-mocked Playwright 2/2; component/SW Vitest 9/9. Not backend E2E or installed service-worker/runtime proof. |
| T06 Scoped handoff and lifecycle | DONE (local artifact commit; no push) | T01–T05 | Source/test baseline `d4b7601864ff0014ae5cba950c421e43f783b813`; this closeout syncs the canonical matrix/checkpoint/result/index/task graph and fresh J1-A01/A03 raw log in a separate scoped local commit. Final diff/evidence/reference checks required; unrelated dirty/untracked WIP stays excluded. Exact final docs commit is reported by verified HEAD, not embedded in this self-referential state file. |

## Findings that constrain implementation

- Retry semantics are covered at the local app-role DB lane (J1-A05/J2-A05): same-key replay, changed-payload conflict, concurrency, stale-state, rollback and permission recheck. `request_id` alone remains correlation—not proof by itself; acceptance relies on the dedicated persisted retry tests.
- D-B reuse-by-reference is preserved: exact document version is associated with multiple same-tenant Dossiers while pinned requirements version/type checks and wrong-tenant denial remain enforced.
- The older standalone `/documents` upload route returns a document without Dossier association (`dossier_id=NULL`); that is not the accepted J1-A02 path. J1-A02 acceptance is the version-bound `/dossiers/{id}/documents` rendered path, verified by persisted readback and DB reuse/tenant tests.
- Historical-file route and lifecycle events are covered with synthetic actors/app-role DB and disposable storage. URL issuance, ASGI response lifecycle, exact server-emitted bytes/hash and browser-read bytes are distinct; ASGI completion is not client receipt.
- Current DB role was non-superuser/no-BYPASSRLS; public RLS policy count was 0. RLS/Forced-RLS remains NOT TESTED and is outside the local J1/J2 acceptance closure.

## Resume order

- The requested J1-A02 and X-A02 reconciliation is closed. Use the current matrix for any future explicitly authorized acceptance work; do not reopen unrelated rows based on this closeout.
- Scoped local commit `d4b7601864ff0014ae5cba950c421e43f783b813` is complete. No push, merge, deploy, or customer-pilot action is authorized. STOP C and customer-pilot NO-GO remain.