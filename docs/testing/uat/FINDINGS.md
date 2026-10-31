# Automated browser findings — 2026-10-31

## 1. Analysis

The two original failures are fixed in the uncommitted source candidate on
`feat/uat-automation-20261031`. The final candidate desktop run passed21/21
executable subcases, including post-restore browser/file verification. This is
local technical verification; serving main5457cf8/schema057 is unchanged.

The full baseline remains **BLOCKED**, not accepted:160controls+14journeys,
with23entries partially mapped to maintained executable subcases. The8owner-
excluded commercial scope groups remain N/A and retained for a later phase.
No complete control, full pilot approval or physical-device sign-off is claimed.

## 2. Solution

- Complaint intake selects an existing provider for a business and derives the
  source from the signed-in role. Provider owners use the existing assignment
  and transition contracts. Saved cases, owner, decision and closure rationale
  remain visible after reload. Native validation requires an appeal decision,
  a decision summary or closure reason at the corresponding step. Irrelevant
  draft rationale is excluded from unrelated transitions; the loaded saved summary
  is preserved on closure.
- Conflict declaration, review and override use the existing authorized APIs.
  Saved declaration state/review reason reload from the server. Business users
  cannot open the register; review/override controls require owner/admin access.
- Shared authenticated writes normalize backend errors, serialize rapid submit
  events and retain input after a rejected write. Lost responses and failed
  post-save refreshes require a register reload before further writes. Request
  generations prevent delayed reads, including token refresh during a write,
  from overwriting the newer saved list. No new backend/schema/API was introduced.
- The runner rejects overlapping invocations before Docker setup. Reports
  materialize inline screenshots/server evidence into private files with safe
  generated names and link them from the HTML summary.

## 3. Risks

The serving forms are **not repaired until an authorized source publication and
release**. No commit, push, merge, deployment, production migration, CI/CD or
scheduler activation was performed. This candidate is explicitly labelled
`uncommitted-uat-candidate`, not a committed-main release.

The existing API remains the authorization and business-policy boundary. Broader
appeal independence, complete certificate/decision/audit/offline workflows,
cross-client concurrency, external integrations and independent business acceptance remain outside this
covered subset. The UI queue shows saved current state; it does not advertise a
nonexistent event-history GET endpoint. Do not infer full workflow coverage from
these transaction checks. Dependency lockfiles were not changed; the build's
cached dependency audit reported3high/20moderate findings without scope triage,
so no dependency-security clearance is claimed here.

## 4. Tests

- Final expanded desktop:21PASS/0FAIL/0SKIP, including synthetic PostgreSQL
  recovery followed by real login, dossier and file SHA256 checks. Recovery
  operation9.782s; Keycloak/storage retained, not full disaster recovery.
- Final mobile-emulation trust subset:8PASS/0FAIL/0SKIP on the same immutable
  frontend image, run after desktop teardown; not physical-device acceptance.
- Frontend suite:371PASS across58files. Runner/report/cleanup/lock regressions:
  25PASS. Scoped ESLint, TypeScript and Docker production build PASS.
- Complaint browser coverage: intake, receipt/reload, CB assignment, complete
  lifecycle, rejected premature closure, protected rationale and audit/event
  sequence; invalid/missing appeal reference and wrong-business denial.
- Conflict browser coverage: declaration/reload, under_review/blocked/cleared,
  override with reason, rejected unnecessary override, unresolved-conflict
  assignment409and cleared/overridden assignment200. Supplemental API checks
  reject foreign CB reads/writes404and non-owner CB review/override403.
- Both forms cover server rejection with input retained and a real saved write
  whose browser response is deliberately lost; reload recovers exactly one row.
  Successful save plus failed list refresh retains a truthful receipt.
- Unit concurrency tests cover rapid double submission and stale session reads
  before/during a write. The during-write test first reproduced stale list
  overwrite, then passed after the generation fix.
- A real second runner invocation was rejected with exit1, no output directory
  and no additional UAT container. Each completed run checks cleanup and unchanged
  pre-existing runtime IDs/images/start times. No customer rows were copied.

Final frontend image: `sha256:2ab20680b1895865686dce074a44919513506c4ea711e16fc89a2eb0729ae45e`; runtime source fingerprint manifest retained
with the image metadata. Backend is the unchanged verified5457cf8 release.
Evidence: `/home/user/Downloads/aminra-uat-trust-fix-20261031/handoff-desktop/report.html` and private logs/manifests in the
parent directory. Mobile evidence is at `/home/user/Downloads/aminra-uat-trust-fix-20261031/handoff-mobile/report.html`.
Generated credentials/traces remain private and must not be
committed or publicly uploaded.

Earlier attempts are retained, not reclassified as clean passes: the first
candidate run14PASS/7FAIL exposed two selector mistakes (wrapped select labels
and the Next.js route announcer); the next run20PASS/1FAIL recorded
`ERR_NETWORK_CHANGED` while isolated environments overlapped. Serial execution
is now enforced. The earlier acceptance report remains historical evidence.

## 5. Improvements

Source remediation and its maintained regression subset are complete locally.
Publish/release only through the explicit manual source workflow when authorized,
then re-run against the committed serving image and verify actual browser access.
Continue full-baseline decomposition separately; retain physical-device,
external-service and professional-judgment boundaries. Do not promote174baseline
controls/journeys to Pass from21subcases.
