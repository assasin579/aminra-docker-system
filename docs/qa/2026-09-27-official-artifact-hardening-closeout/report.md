# AMINRA Official Artifact Hardening Closeout

Date: 2026-09-26 local host time / evidence path 2026-09-27
Repo: `/home/user/Documents/aminra-docker-system`
Verdict: **LOCAL SANDBOX PASS for covered official-artifact hardening lanes; production/customer-pilot remains PARTIAL / not GO.**

## Scope / acceptance criteria

P0 live UAT:
- Credentialed business token uploads a real document.
- Business submits and approves the document.
- Approval creates an immutable official artifact row/file.
- Official artifact list returns the artifact by `source_document_id`.
- Official artifact file download returns the approved bytes.
- Source document delete is blocked with `409` once official artifact exists.
- QA credentials remain gitignored/redacted.

P1 observability:
- Official artifact creation emits counters for created/existing/failure paths.
- Artifact creation failure logs exception context and fails closed.
- Focused regression proves failure metric/log/raise behavior.

P2 tech debt:
- Sentry Next.js 16 deprecation cleanup: use `@sentry/nextjs/config`, `webpack.treeshake.removeDebugLogging`, `instrumentation.ts`, `instrumentation-client.ts`, and `app/global-error.tsx`.
- Route-mocked Playwright specs stop using obviously invalid placeholder token strings where scoped.

## Evidence

Final live UAT:
- Report: `/home/user/Documents/aminra-docker-system/docs/qa/2026-09-27-official-artifact-live-uat-final/report.md`
- Status: `/home/user/Documents/aminra-docker-system/docs/qa/2026-09-27-official-artifact-live-uat-final/status.tsv`
- Playwright/API log: `/home/user/Documents/aminra-docker-system/docs/qa/2026-09-27-official-artifact-live-uat-final/evidence/terminal/playwright-official-artifact-live-uat.txt`

Final status rows:
- `CREDENTIALS PASS` — loaded gitignored QA credential keys; values redacted.
- `FEATURE-FLAG PASS` — `document_versioning_v1` enabled for QA business tenant only.
- `RUNTIME-BACKEND PASS` — backend health responded.
- `OFFICIAL-ARTIFACT-UAT PASS` — approval created artifact; list/download succeeded; source delete returned `409`.

Source/build gates:
- Frontend `npm run build -- --webpack` PASS on Next.js `16.3.5`.
- Frontend `npm run lint` PASS with `--max-warnings=0`.
- Frontend `npx tsc --noEmit --pretty false` PASS.
- Backend focused gate PASS: `8 passed` for `backend/tests/test_official_artifacts_service.py` and `backend/tests/test_official_artifact_separation_contract.py`.
- Package-lock resolution sanity PASS: `npm ci --dry-run --ignore-scripts --legacy-peer-deps`.
- `git diff --check` PASS.

Runtime state:
- Docker Compose shows backend/frontend/Postgres/Qdrant/Redis/Keycloak running; backend/frontend healthy after rebuild/recreate.
- Recent backend/frontend fatal/error/exception log scan for the final UAT window returned no matches.

Secret hygiene:
- Added-line secret-assignment scan: PASS.
- Untracked sensitive-path scan: PASS.
- Final UAT evidence prints redacted env shape only; no password/token values are stored in the report path.

## Changed areas

Backend:
- `backend/services/official_artifacts.py` adds Prometheus counter coverage and failure logging around artifact creation.
- `backend/tests/test_official_artifacts_service.py` adds regression coverage for failure metric/log/raise behavior.

Frontend / Next.js / Sentry:
- `frontend/aminra-web/next.config.ts` switches Sentry config import and removes deprecated logger option.
- `frontend/aminra-web/instrumentation.ts`, `instrumentation-client.ts`, and `app/global-error.tsx` add Next/Sentry runtime hooks.
- `frontend/aminra-web/sentry.client.config.ts` removed.
- `frontend/aminra-web/package.json` and `package-lock.json` updated for `next@16.3.5` and `@sentry/nextjs@10.74.0`.

UAT:
- `frontend/aminra-web/e2e/document-official-artifact-live-uat.spec.ts` is the maintained credential-gated Playwright API spec.
- `scripts/qa/run-official-artifact-live-uat.sh` is the secret-safe runner.

## Known boundaries / risks

- This is **not production/customer-pilot GO**. It proves local sandbox behavior for the covered official-artifact lane only.
- P1 observability is source/runtime metric/log coverage, not deployed Prometheus/Alertmanager rule wiring.
- `npm audit --omit=dev` still reports production dependency findings: `0 critical / 6 high / 1 moderate / 1 low`. Direct production issue includes `axios`; transitive findings include `@xmldom/xmldom`, `form-data`, `postcss`, `browserslist`, `nanoid`, `@babel/core`, and `baseline-browser-mapping`. Treat dependency remediation as a separate controlled branch/gate, not an opportunistic force-fix.
- The live UAT intentionally enables `document_versioning_v1` for the QA business tenant only. Do not generalize that flag to production without rollout approval.
- Maker-checker independence is not asserted by this UAT because current local policy allows the business user to approve the submitted document. If policy tightens, add a separate role-independence UAT.

## Verdict

PASS for local sandbox P0/P1/P2 closeout evidence:
- P0 credentialed approve → official artifact → list/download → source delete-block: PASS.
- P1 official artifact creation failure metric/log/raise coverage: PASS.
- P2 Sentry deprecation cleanup and scoped Playwright token-noise reduction: PASS.

PARTIAL for broader release readiness:
- production/customer-pilot GO remains blocked by dependency security triage, deployed alert wiring, SMTP/customer onboarding, edge/CDN SLO, and broader browser/mobile/role coverage.
