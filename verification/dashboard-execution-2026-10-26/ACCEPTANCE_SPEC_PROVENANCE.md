# J1/J2 acceptance-spec provenance check

**Checked:** 2026-10-29 (documentation-only; no application tests/runtime/DB rerun)
**Workspace:** `/home/user/.cache/aminra-dashboard-integrated`
**Branch / current handoff HEAD before this document:** `dashboard/execution-2026-10-26` / `bcf2fe5a1f81e142046cfe2b95d1114e7379273d`
**Accepted source/test baseline:** `d4b7601864ff0014ae5cba950c421e43f783b813`
**Result:** No source-authenticated acceptance spec was recovered. The per-ID spec comparison is therefore **UNRESOLVED**, not “matched”. Do not treat this report or the matrix as a reconstructed/original spec.

## Sources and lineage checked

1. **Previously cited cached document:** `/home/user/.hermes/cache/documents/doc_777a05270a15_aminra-dashboard-spec.md`. The path is absent. A local filename search under `/home/user/.hermes`, `/home/user/Documents`, and `/home/user/.cache` found no matching document name or document ID. No file bytes are available; content hash, version, and commit are consequently unavailable.
2. **Workspace Git history:** searched all locally available refs and full history for the former filename/ID, likely spec path names, `J1-A01`, and the distinctive matrix wording `Upload/chọn exact version vào đúng Dossier`. The wording appears in the acceptance-matrix history (including source-baseline commit `d4b7601864ff0014ae5cba950c421e43f783b813`) as matrix text, not as a separate source document. No add/rename/move/delete lineage for the cited cached file or an equivalent spec path was found. Local branch: `dashboard/execution-2026-10-26`; no other local branch contains the named spec artifact. Remote refs were not fetched; no remote document is claimed inspected.
3. **Tracked handoff files:** `J1_J2_CHECKPOINT.md`, `J1_J2_ACCEPTANCE_MATRIX.md`, `J1_J2_EXECUTION_RESULT.md`, `J1_J2_TASKS.md`, and `INDEX.md` were read. They preserve the 18-ID matrix, scoped evidence, and repeated historical citations to the missing cached path; they do not contain the original complete spec or a verifiable copy/version/hash. The checkpoint explicitly says the cached file was absent at final reconciliation.
4. **Candidate classification:** the 18-row acceptance matrix is the current approved denominator and evidence ledger, but it is a downstream matrix and cannot establish the source text merely because it repeats 18 IDs or quotes short acceptance excerpts. Checkpoint/result/task graph are summaries, not independent specification sources. No candidate is promoted to “original” or “amendment” without provenance.

## Per-ID comparison

Because no source-authenticated spec bytes/version were found, acceptance wording, required boundary, mandatory conditions/limits, and approved scope changes cannot be independently compared. “Unresolved” below means source-to-matrix comparison was not possible; it does **not** mean the current matrix row failed, nor does it erase the previously recorded scoped evidence/verdict.

| ID | Spec with verified provenance | Current matrix | Comparison |
|---|---|---|---|
| J1-A01 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J1-A02 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J1-A03 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J1-A04 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J1-A05 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J1-A06 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J1-A07 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J1-A08 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J2-A01 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J2-A02 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J2-A03 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J2-A04 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J2-A05 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| J2-A06 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| X-A01 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| X-A02 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| X-A03 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |
| X-A04 | Not recovered; version/hash unavailable | Present; scoped PASS retained | Unresolved |

No specific added/omitted criterion or boundary delta can be established from the available source set. No R1–R12 mapping is inferred. No acceptance text, verdict, or raw evidence was rewritten on the basis of an unverified reconstruction.

## Disposition and minimum unblock

- Preserve existing matrix denominator and all per-row PASS results **only within their recorded local synthetic/API+DB/browser boundaries**. Record the missing source lineage as a limitation on traceability; this check does not broaden or revoke those verdicts.
- Do not create a replacement spec, call matrix excerpts verbatim source, change the acceptance denominator, rerun application/browser/DB tests, or reopen implementation.
- To close source traceability, the owner/source custodian must provide the original artifact or a trustworthy archive reference with its provenance/version (ideally original path plus commit/export metadata). Then hash the bytes and perform an actual clause-by-clause comparison against all 18 IDs, including boundary, mandatory conditions, limits, and approved amendments. That source is the only outstanding dependency for this document-reconciliation objective.
- STOP C and customer-pilot NO-GO remain unchanged. No RLS, live OIDC, production, release, or pilot claim is made.
