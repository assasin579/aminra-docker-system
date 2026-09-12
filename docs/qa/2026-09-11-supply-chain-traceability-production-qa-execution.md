# AMINRA Supply-Chain Traceability — Production QA Execution File

**Date:** 2026-09-11  
**Owner:** Hermes Agent / QA Lead  
**Codebase:** `/home/user/Documents/aminra-docker-system`  
**Canonical local URL:** `http://localhost:3100`  
**Canonical public sandbox URL:** `https://dev-web.silvergem.org`  
**Target module:** supply-chain traceability, sealed public trace, QR/public trace, supplier/NCC eligibility, batch/lot lifecycle, audit/security boundaries.

---

## 0. How to use this file

This is a self-contained execution prompt/checklist for a Hermes agent or coding/QA subagent. Execute from:

```bash
cd /home/user/Documents/aminra-docker-system
```

Hard rules:

1. **Do not commit, push, deploy, publish, delete real data, or rotate secrets unless the founder explicitly authorizes it.**
2. Use QA-prefixed deterministic fixtures only.
3. Never print passwords, cookies, bearer tokens, refresh tokens, Keycloak client secrets, `.env` contents, or raw auth headers.
4. If credentials are missing, mark affected role-browser/live cases as `BLOCKED`; do not downgrade them to `PASS`.
5. Treat HTTP 200 as weak evidence. For traceability, assert rendered markers, data ownership, sealed snapshot source, public fail-closed behavior, and audit side effects.
6. For any product-code change, follow RED-GREEN-REFACTOR: write/extend a failing test first, verify it fails for the expected reason, then implement minimal code, then run focused and regression gates.
7. Final status may only be `DONE` when all required P0/P1 gates pass. Otherwise report `PARTIAL`, `BLOCKED`, or `NO-GO` with exact gaps.

---

## 1. Mission

Act as a 20-year QA lead and production-readiness gatekeeper. Validate whether AMINRA's supply-chain traceability module is production-quality for a regulated Halal/supply-chain SaaS.

Do not only test the happy path. Prove these invariants:

1. Public trace output is based on **opaque public trace IDs**, not enumerable/internal IDs.
2. Public trace is **fail-closed** until the batch is sealed and explicitly public-enabled/published.
3. Public trace renders from an **immutable sealed snapshot**, not mutable live supplier/material/batch tables.
4. Supplier/NCC eligibility is **CB/provider-authoritative**, not business self-asserted.
5. Cross-tenant and cross-provider boundaries are enforced.
6. Sealed batches reject unsafe post-seal mutations.
7. Audit trail records critical actions and does not leak secrets.
8. Runtime/public sandbox behaves consistently with source and automated tests.

---

## 2. Required outputs

Create an evidence pack:

```text
docs/qa/2026-09-11-supply-chain-traceability-production/
  report.md
  defects/DEFECTS.md
  evidence/
    terminal/
    api/
    screenshots/
    browser-console/
    performance/
  test-data/created-records.md
  raw/
```

The final `report.md` must include:

- Executive verdict: `GO`, `CONDITIONAL GO`, `PARTIAL`, `NO-GO`, or `BLOCKED`.
- Environment: branch, commit, dirty tree, container/service status, URLs, DB migration head.
- Scope and out-of-scope.
- Test matrix summary by category with PASS/FAIL/BLOCKED/NOT RUN counts.
- P0/P1 defects with repro steps and evidence paths.
- Role/RBAC matrix.
- Public trace matrix.
- Sealed snapshot matrix.
- Audit/compliance findings.
- Performance/security caveats.
- Exact commands run and important outputs.
- Known unverified gaps.
- Final recommendation and next actions by priority.

---

## 3. Startup discovery and safety checks

Run and record:

```bash
date -Is
git status --short
git branch --show-current
git rev-parse --short HEAD
docker compose ps aminra-backend aminra-frontend arq-worker postgres-db qdrant-db keycloak redis
curl -fsS http://localhost:8100/health
curl -sS -o /tmp/aminra-root.html -w 'HTTP %{http_code}\n' http://localhost:3100/
curl -sS -o /tmp/aminra-public.html -w 'HTTP %{http_code}\n' https://dev-web.silvergem.org/
```

Also identify current migration head. Prefer the project wrapper because it sources the Vault/dev DB environment correctly:

```bash
./scripts/db-migrate.sh current
```

If you must run inside the container directly, source the env first:

```bash
docker compose exec -T aminra-backend sh -lc '. /vault/secrets/env.sh 2>/dev/null; alembic current'
```

If services are down:

- Record `BLOCKED: runtime unavailable` for runtime/browser/live cases.
- Do not run destructive recovery unless explicitly authorized.
- Source-level tests may still run.

---

## 4. Verdict ladder

Use these labels honestly:

- `GO`: all P0 and required P1 gates pass; no unresolved P0/P1 defects.
- `CONDITIONAL GO`: core sandbox/demo flow passes; only documented P2/P3 caveats remain.
- `PARTIAL`: meaningful evidence collected but coverage gaps remain.
- `NO-GO`: any P0/P1 blocker in public trace, RBAC, tenant isolation, sealed snapshot, data integrity, auth, or critical runtime.
- `BLOCKED`: environment/credentials/tools missing prevent meaningful validation.

Never collapse source-test green into production-ready green. Source, build, integration, runtime, browser, and security evidence are separate lanes.

---

## 5. Priority execution plan

### P0 — must run first

1. Source/domain invariant tests.
2. Public trace API fail-closed tests.
3. Sealed snapshot immutability tests.
4. Supplier/NCC CB-authority tests.
5. RBAC + tenant + provider-boundary tests.
6. Migration/data integrity tests.
7. Runtime smoke against local and public sandbox.
8. High-signal log scan.

### P1 — run after P0 green or to confirm failure blast radius

1. Full API contract matrix.
2. Integration flow from supplier/cert/material/batch/seal/publish/public trace.
3. Browser E2E smoke by role.
4. Audit/compliance matrix.
5. Public trace UI/mobile/QR behavior.
6. Basic security attack cases.

### P2 — production-scale confidence

1. Performance/load baseline.
2. Resilience/failure-mode tests.
3. Accessibility/localization checks.
4. Observability/monitoring checks.

---

## 6. Detailed test matrix

### A. Domain invariant unit tests — target 45 cases

#### A1. Supplier / NCC eligibility — 10 cases

- NCC with active certificate, correct tenant, correct scope is eligible.
- NCC with multiple certs selects currently active in-scope cert.
- Expired old cert + active renewed cert is eligible.
- No certificate is ineligible.
- Expired certificate is ineligible.
- Revoked/suspended certificate is ineligible.
- Active certificate with wrong material/category scope is ineligible.
- Active certificate from other tenant/provider is ineligible.
- Business self-set `verified=true` without authority evidence remains ineligible.
- Provider without source authority cannot confirm supplier eligibility.

#### A2. Material eligibility — 8 cases

- Material with eligible supplier is allowed.
- Material switching from eligible supplier to ineligible supplier is rejected.
- Missing supplier is rejected when traceability is required.
- Cert expired at production date is rejected even if currently active.
- Cert not yet effective at production date is rejected.
- Material category outside cert scope is rejected.
- Optional/non-critical material behavior matches documented policy.
- Multi-material batch fails if one material is ineligible.

#### A3. Batch/lot state machine — 10 cases

- Draft → in production → QC passed → sealed → public-enabled/published path works.
- Draft can edit allowed fields.
- In-production status limits edits.
- QC failed cannot seal.
- Sealed cannot mutate source material links.
- Published cannot unpublish unless policy explicitly allows.
- Archived/unpublished not visible publicly.
- Batch without material trace cannot seal.
- Batch missing production date/lot number cannot seal.
- Duplicate lot within same tenant/product conflicts.

#### A4. Public trace ID / QR invariant — 7 cases

- Public trace ID is opaque, not internal UUID/DB ID/tenant-local business code.
- Public trace ID is globally unique.
- Internal batch UUID does not resolve as public trace unless explicitly mapped and allowed.
- Nonexistent public ID returns 404.
- Malformed public ID returns 404/422, never 500.
- Case-sensitivity policy is enforced deterministically.
- Public output does not expose internal tenant/user/batch IDs.

#### A5. Sealed snapshot rules — 10 cases

- Seal creates complete supplier/material/certificate/batch/event snapshot.
- Snapshot stores certificate status at seal time.
- Supplier name mutation after seal does not change public output.
- Certificate revocation after seal follows policy: immutable snapshot plus risk notice or controlled status.
- Product/image mutation after seal follows documented snapshot policy.
- Adding chain event after seal is rejected or creates explicit revision, never silent overwrite.
- Second seal request is idempotent or conflicts safely.
- Snapshot has version/hash.
- Snapshot hash changes when pre-seal data changes.
- Snapshot hash does not change after unrelated upstream mutation.

### B. API contract tests — target 55 cases

#### B1. Public trace API — 15 cases

- Published + sealed + public-enabled trace returns 200.
- Unpublished batch returns 404.
- Sealed but not public-enabled returns 404.
- Public-enabled but unsealed returns 404.
- Archived/revoked trace returns 404 or 410 per policy.
- Invalid short ID returns 404/422.
- SQL injection-shaped ID returns controlled 404/422.
- Path traversal-shaped ID returns controlled 404/422.
- Upper/lowercase behavior matches policy.
- Response has no internal IDs.
- Response has no private notes.
- Response has no auth-only documents.
- Response has canonical batch summary.
- Chain events sorted deterministically.
- Certificate snapshot fields match schema.

#### B2. Admin/batch APIs — 12 cases

- Create valid batch returns 201/200.
- Missing required field returns 422.
- Invalid date returns 422.
- Duplicate lot within scope returns 409.
- Same lot across separate tenant allowed if policy says so.
- Update draft succeeds.
- Update sealed restricted field returns 403/409.
- Add material to draft succeeds.
- Add ineligible material returns 400/409.
- Seal valid batch succeeds.
- Seal invalid batch returns 409 with machine-readable reason.
- Publish/public-enable sealed batch succeeds.

#### B3. Supplier/material APIs — 10 cases

- Create supplier with required fields.
- Update supplier profile.
- Attach certificate evidence.
- Remove certificate evidence blocked when used by sealed batch unless snapshot-retained policy explicitly supports it.
- Expire/suspend certificate updates eligibility for new operations.
- Business cannot self-approve regulatory eligibility.
- Provider can update only owned/authorized evidence.
- Cross-tenant supplier read denied.
- Cross-tenant supplier mutation denied.
- List endpoint respects tenant filters and pagination bounds.

#### B4. Chain event APIs — 10 cases

- Append receive event.
- Append processing event.
- Append inspection event.
- Append shipping/export event.
- Invalid event timestamp ordering rejected or flagged per policy.
- Unknown actor rejected.
- Missing required location rejected or explicitly incomplete.
- Draft event edit allowed.
- Sealed event edit rejected.
- Event list sorted stable.

#### B5. Error response contract — 8 cases

- 400/409/422 include machine-readable `code` or equivalent.
- Validation errors never expose stack traces.
- Unauthorized returns 401.
- Forbidden returns 403.
- Hidden/foreign resource returns 404 if anti-enumeration policy.
- Rate limit returns 429.
- Dependency failure returns controlled 503.
- Correlation/request ID present where available.

### C. RBAC, tenant isolation, and authority tests — target 40 cases

Roles: anonymous, business owner, business staff/sub-user, provider/CB, provider auditor/staff, platform admin, suspended user.

#### C1. Anonymous boundary — 6 cases

- Anonymous only reads valid public trace.
- Anonymous cannot read admin batch list.
- Anonymous cannot read private supplier detail.
- Anonymous cannot mutate chain events.
- Anonymous cannot enumerate public IDs effectively.
- Malformed token does not bypass anonymous boundary.

#### C2. Business role — 10 cases

- Business creates draft batch in own tenant.
- Business reads own batch.
- Business cannot read another tenant's batch.
- Business cannot self-approve CB/regulatory eligibility.
- Business cannot publish if role lacks publish permission.
- Business owner has higher permissions than staff.
- Business staff constrained by permission.
- Suspended business user blocked.
- Business cannot mutate sealed snapshot/materials.
- Business cannot delete evidence used by sealed batch unless policy supports retained snapshots.

#### C3. Provider/CB role — 10 cases

- Provider reads suppliers/certs under its authority.
- Provider issues/updates certificate only with source authority.
- Provider B cannot take over Provider A eligibility.
- Provider staff cannot perform owner-only actions without role.
- Provider auditor is read-only where required.
- Provider cannot access business private production notes outside scope.
- Provider status changes affect new eligibility decisions.
- Provider actions write audit records.
- Provider cannot publish business public trace unless policy allows.
- Provider losing authority blocks future mutations.

#### C4. Platform admin — 8 cases

- Admin can read cross-tenant oversight surfaces.
- Admin can suspend tenant/user.
- Admin critical mutation requires audit reason if implemented.
- Admin impersonation/break-glass is audited if implemented.
- Admin cannot bypass sealed immutability without explicit break-glass/revision flow.
- Break-glass requires reason.
- Admin action appears in audit trail.
- Admin API responses do not expose secrets.

#### C5. Token/session edge — 6 cases

- Expired token returns 401.
- Wrong audience returns 401.
- Wrong issuer returns 401.
- Missing tenant claim returns 403/422.
- Raw realm roles preserved where admin guards depend on them.
- Disabled user with old token blocked according to policy/window.

### D. Database, migration, and data integrity tests — target 25 cases

- Fresh migration succeeds.
- Upgrade migration from previous head succeeds.
- Rollback path succeeds where supported.
- Required FK constraints exist.
- Tenant FK/index exists on trace entities.
- Unique index for public trace ID exists.
- Unique index for lot policy exists.
- Snapshot table/fields support immutable sealed data.
- Audit references valid entity/actor.
- Deleting supplier used by batch is restricted or snapshot-retained safely.
- Deleting cert used by sealed snapshot is restricted or snapshot-retained safely.
- Cascade delete cannot remove audit trail.
- Large fields bounded.
- Snapshot JSON schema constrained/validated.
- Timestamps autopopulate.
- UTC storage enforced or documented.
- Soft delete filters default list queries.
- Archived records recoverable if policy.
- Migration preserves existing batches.
- Backfill creates public trace IDs only for eligible legacy batches.
- Backfill skips incomplete data with report.
- Null legacy fields handled safely.
- Concurrent inserts cannot duplicate public IDs.
- Index supports public trace lookup.
- Index supports tenant batch list.

### E. Integration tests with real DB/services — target 30 cases

- Supplier → certificate → material eligibility computed.
- Material/product/batch → seal → publish → public trace reads snapshot.
- Revoke cert after publish → public output follows policy.
- Supplier update after seal → public output unchanged.
- Product update before seal → snapshot includes new product data.
- Cross-tenant batch lookup fails.
- Provider authority update propagates to eligibility.
- Audit log generated for create/update/seal/publish.
- Media/document upload attaches to certificate.
- Private document absent from public trace.
- Public document present only after publish.
- Batch search/filter works.
- Pagination deterministic.
- Concurrent same-lot creation: one success, one conflict.
- Concurrent seal: one success; second idempotent/conflict.
- Cache invalidates after publish.
- Cache does not serve stale unpublished data.
- Search/Qdrant dependency failure does not break core trace read if non-critical.
- DB unavailable returns controlled 503.
- Object storage failure returns controlled error.
- Worker processes audit/notification task.
- Failed worker task retries.
- Idempotency key prevents duplicate chain event.
- Transaction rollback on partial batch creation failure.
- Multi-material batch persists all-or-none.
- Public trace reads sealed snapshot, not mutable live tables.
- Response sorting stable across repeated calls.
- Timezone conversion correct.
- Locale field selection works if supported.
- Test fixture cleanup leaves DB clean.

### F. E2E role workflows — target 25 cases

#### F1. Core happy paths — 8 cases

- Business creates supplier/material/batch.
- Provider validates/updates certificate eligibility.
- Business completes production events.
- Business seals batch.
- Business public-enables/publishes trace.
- Anonymous scans/opens public QR trace.
- Admin reviews audit trail.
- Business downloads/opens QR label.

#### F2. Negative workflows — 9 cases

- Business tries to seal batch with ineligible supplier: blocked.
- Business tries to publish unsealed batch: blocked.
- Business tries to edit sealed material: blocked.
- Provider without authority tries approve supplier: blocked.
- Staff without publish permission tries publish: blocked.
- Anonymous tries admin URL: blocked.
- Tenant A opens Tenant B batch URL: blocked.
- Expired certificate blocks new batch.
- Revoked certificate triggers warning/block per policy.

#### F3. Recovery/lifecycle — 8 cases

- Draft batch corrected after validation error then sealed.
- Certificate renewed restores eligibility.
- Unpublished trace becomes visible after public-enable/publish.
- Archive/unpublish removes public visibility.
- Break-glass/admin correction creates revision/audit if implemented.
- Batch revision creates new public snapshot version if policy.
- User resumes partial draft safely.
- Failed upload retry succeeds without duplicate evidence.

### G. Public trace UI/UX/browser tests — target 20 cases

- Valid public trace page loads.
- Product/batch identity clear.
- Timeline order correct.
- Supplier/certificate section clear.
- Halal/certification wording not misleading.
- Missing optional image has professional fallback.
- Long names wrap without breaking layout.
- Mobile viewport has no horizontal overflow.
- QR/deep link opens correct page.
- Invalid ID shows safe not-found state.
- Expired/revoked notice appears per policy.
- Private/internal fields absent from rendered HTML.
- Loading state not stuck.
- Error state no stack leak.
- Print/share layout acceptable.
- Locale switch preserves trace ID if supported.
- Date/time consistent.
- Badge/color semantics clear.
- Visual regression screenshot captured.
- Durable public trace marker exists, e.g. `data-trace-public-status` or equivalent.

### H. Security tests — target 30 cases

#### H1. Input attack — 8 cases

- SQL injection-shaped public ID.
- NoSQL/JSON injection-shaped filters.
- XSS in supplier name.
- XSS in chain event note.
- Path traversal filename.
- Oversized payload rejected.
- Invalid content type rejected.
- Unicode/confusable IDs handled safely.

#### H2. Auth/RBAC attack — 8 cases

- Token role tampering rejected.
- URL/body tenant ID cannot override token tenant.
- Horizontal privilege escalation blocked.
- Vertical privilege escalation blocked.
- Replay old token after disable blocked per policy.
- CSRF protection validated if cookie-based mutations exist.
- CORS restricts origins.
- Public endpoint rejects privileged query expansion.

#### H3. Public enumeration/privacy — 6 cases

- Sequential IDs not usable.
- High-rate invalid trace requests rate-limited.
- 404 timing does not reveal unpublished records materially.
- Public response strips internal UUIDs.
- Public response strips private documents.
- Public response strips staff notes/audit internals.

#### H4. File/document security — 5 cases

- Dangerous file type rejected/quarantined if scanner exists.
- Private certificate document URL requires auth.
- Public document URL only available after publish.
- Signed URL expiry enforced if used.
- File metadata does not leak local paths.

#### H5. Secrets/log safety — 3 cases

- Error logs do not print tokens.
- API response does not print env/config.
- Audit log does not store secrets/raw passwords.

### I. Performance/load tests — target 15 cases

Suggested targets:

- Public trace p95 < 500ms under normal load.
- Public trace p99 < 1.5s under burst.
- Error rate < 0.1%.

Cases:

- Single public trace cold request.
- Public trace warm cache request.
- 100 concurrent public trace reads.
- 500 concurrent public trace reads.
- 1,000 invalid trace reads/min with rate limit.
- Admin batch list with large fixture.
- Supplier search with large fixture.
- Public ID lookup index verified.
- Seal operation under concurrent users.
- Publish operation under concurrent users.
- Large batch with 100 materials/events.
- Large snapshot payload.
- Media loading does not block API critical path.
- Worker queue under 1k audit events.
- 2–4 hour soak has no memory leak if feasible.

### J. Resilience/failure-mode tests — target 15 cases

- DB unavailable → controlled 503.
- Redis/cache unavailable → controlled degradation.
- Object storage unavailable during upload → no partial evidence.
- Worker unavailable → main transaction consistent.
- Qdrant/search unavailable → trace read unaffected if non-critical.
- Timeout during seal → rollback or idempotent retry.
- Timeout during publish → no half-public state.
- Duplicate retry with idempotency safe.
- App restart during background job resumes/retries.
- Migration failure avoids half-upgraded app.
- Cache stale after unpublish does not serve public data.
- Clock skew around cert expiry handled.
- IdP unavailable blocks authenticated mutation safely.
- Log/metric failure does not break business transaction.
- Circuit breaker/backoff avoids cascading failure.

### K. Auditability/compliance tests — target 20 cases

- Create supplier audit logged.
- Update supplier audit logged.
- Attach certificate audit logged.
- Change certificate status audit logged.
- Create batch audit logged.
- Add/remove material audit logged.
- Add chain event audit logged.
- Seal batch audit logged.
- Publish/public-enable trace audit logged.
- Unpublish/archive audit logged.
- Failed unauthorized action logged appropriately.
- Break-glass requires reason if implemented.
- Audit includes actor, role, tenant, timestamp, entity, action.
- Audit excludes secrets.
- Audit immutable to normal users.
- Audit query by batch works.
- Audit query by actor works.
- Snapshot version links to audit event.
- Audit export works if required.
- Retention policy documented/enforced.

### L. Accessibility tests — target 10 cases

- Public trace keyboard navigable.
- Focus order logical.
- QR/deep-link page has clear heading.
- Status badge contrast passes WCAG AA.
- Screen reader labels for certificate/status.
- Timeline readable without color-only meaning.
- Error page accessible.
- Mobile touch targets >= 44px.
- Reduced motion respected.
- Language attribute/locale correct.

### M. Localization tests — target 10 cases

- Default locale renders.
- Vietnamese labels accurate.
- English labels accurate.
- Missing translation fallback safe.
- Locale-specific date format correct.
- Certificate/status terminology correct.
- Locale switch preserves trace ID if implemented.
- Long Vietnamese text wraps.
- Mixed Latin/Vietnamese names render correctly.
- API locale behavior documented or tested.

### N. Observability tests — target 10 cases

- Request/correlation ID present.
- Public trace 404/5xx metrics emitted.
- Seal/publish metrics emitted.
- RBAC denied metric/log emitted.
- High invalid trace scan alert threshold exists.
- Worker failure alert exists.
- DB latency metric exists.
- Audit write failure alert exists.
- Structured logs include safe tenant/entity identifiers.
- Dashboard/runbook links documented.

### O. Regression/smoke tests — target 15 cases

- Backend health reports DB connected.
- Public trace valid fixture returns 200.
- Public trace invalid/non-UUID returns 404.
- Admin auth smoke.
- Business auth smoke.
- Provider auth smoke.
- Create draft batch fixture.
- Seal deterministic fixture.
- Public-enable/publish deterministic fixture.
- Public rendered marker exists.
- Cross-tenant deny fixture.
- Ineligible supplier seal blocked.
- Sealed snapshot unchanged after supplier update.
- API docs/schema generation valid if present.
- Logs have no high-signal errors after smoke.

---

## 7. Suggested command gates

Adapt commands to actual project scripts discovered in repo. Record exact commands and outputs.

### Backend focused supply-chain gates

```bash
docker compose exec -T aminra-backend pytest backend/tests -q -k 'supply_chain or public_trace or trace or supplier_eligibility or batch or sealed'
```

If tests run inside `/app` rather than repo root:

```bash
docker compose exec -T aminra-backend pytest tests -q -k 'supply_chain or public_trace or trace or supplier_eligibility or batch or sealed'
```

### Migration gate

```bash
./scripts/db-migrate.sh current
```

For disposable local DB clones only, after confirming backup/sandbox scope:

```bash
./scripts/db-migrate.sh downgrade -1
./scripts/db-migrate.sh upgrade head
```

Do not run downgrade/upgrade against non-disposable customer/pilot data without explicit approval.

### Frontend gates

```bash
cd frontend/aminra-web
npm test -- --runInBand 2>/dev/null || npm test
npm run lint
npm run build
```

### Runtime smoke

```bash
curl -fsS http://localhost:8100/health
curl -sS -o /tmp/aminra-local-home.html -w 'HTTP %{http_code}\n' http://localhost:3100/
curl -sS -o /tmp/aminra-public-home.html -w 'HTTP %{http_code}\n' https://dev-web.silvergem.org/
curl -sS -o /tmp/aminra-trace-invalid.html -w 'HTTP %{http_code}\n' https://dev-web.silvergem.org/api/supply-chain/public/trace/ABC123
```

### High-signal log scan

```bash
docker compose logs --since 30m aminra-backend aminra-frontend arq-worker postgres-db qdrant-db \
  | grep -Ei 'Traceback|Unhandled|ECONNREFUSED|permission denied|foreignkeyviolation|fatal|panic|error' || true
```

### Git hygiene

```bash
git diff --check
git status --short
```

---

## 8. Defect severity model

- **P0 Critical:** public leak, cross-tenant leak, RBAC bypass, wrong public trace data, mutable sealed snapshot, unauthorized publish/edit/delete, production service down.
- **P1 High:** core trace flow broken, seal/publish flow broken, provider/business workflow broken, audit missing for critical action, security validation weak with feasible exploit.
- **P2 Medium:** important UX/API/validation/performance issue with workaround.
- **P3 Low:** cosmetic, copy, minor visual/accessibility issue not affecting trust/safety.

Each defect must include:

```text
ID:
Severity:
Title:
Role:
URL/API:
Preconditions:
Steps to reproduce:
Expected:
Actual:
Evidence:
Risk:
Recommended fix:
Retest notes:
```

---

## 9. Production readiness decision rules

Declare `NO-GO` if any of these occur:

- Public trace returns draft/unsealed/unpublished data.
- Public trace uses mutable live tables and changes after upstream mutation without explicit revision policy.
- Public response exposes internal UUIDs, tenant IDs, private documents, staff notes, or audit internals.
- Business can self-approve regulatory/supplier eligibility.
- Provider without authority can approve/takeover supplier eligibility.
- Tenant A can read/mutate Tenant B traceability data.
- Sealed batch can be materially changed without break-glass/revision/audit.
- Missing audit for seal/publish/cert status/provider authority mutation.
- Runtime public sandbox fails core smoke.

Declare `PARTIAL` if:

- Source tests pass but live/browser role credentials are missing.
- Runtime smoke passes but role/RBAC negative matrix was not executed.
- E2E passes but performance/security/resilience gates are not yet run.

Declare `GO` only if:

- P0 gates pass.
- Required P1 gates pass.
- No P0/P1 defects remain open.
- Evidence pack is complete and reproducible.

---

## 10. Final response schema for Hermes agent

When done, respond with:

```text
## Verdict
<GO | CONDITIONAL GO | PARTIAL | NO-GO | BLOCKED>

## What I verified
- ...

## Test result summary
- P0: PASS x / FAIL y / BLOCKED z
- P1: PASS x / FAIL y / BLOCKED z
- P2: PASS x / FAIL y / BLOCKED z

## Critical findings
- P0: ...
- P1: ...

## Evidence pack
- Report: <path>
- Defects: <path>
- Screenshots/logs: <path>

## Commands run
- ...

## Unverified gaps
- ...

## Recommended next actions
- P0: ...
- P1: ...
- P2: ...
```

---

## 11. Minimum acceptable first-pass scope

If time is constrained, do not pretend to execute all 365 cases. Execute this first-pass minimum and label remaining coverage honestly:

1. Startup/env checks.
2. Backend focused supply-chain/public-trace/sealed snapshot tests.
3. Migration current + safe rollback/upgrade if local sandbox and backup available.
4. Frontend lint/build and relevant test suite.
5. Local/public runtime smoke.
6. Public invalid trace fail-closed smoke.
7. Cross-tenant/provider/RBAC focused tests where test harness exists.
8. Log scan.
9. QA report with explicit unrun matrix.

Minimum first-pass target: **P0 production-safety confidence**, not full production-scale confidence.
