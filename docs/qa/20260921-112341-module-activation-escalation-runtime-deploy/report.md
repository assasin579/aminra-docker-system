# 2026-09-21 — Module Activation Operator Escalation Runtime Deploy/UAT

## Verdict

**PASS for local sandbox runtime deploy + authenticated escalation API smoke + credentialed browser UAT.**

**Production/customer-pilot remains PARTIAL**, because escalation is still in-app DB notification only; external operator channel policy, package/billing semantics, SMTP/customer onboarding, edge/CDN SLO, and dependency/security backlog remain unresolved.

## Scope

- Backup sandbox Postgres before migration/deploy.
- Build/recreate AMINRA backend/frontend images.
- Apply migration `046_module_activation_escal` to the actual runtime DB.
- Verify schema columns and local/public health.
- Enable scoped runtime module guards for the UAT lane:
  - `MODULE_GUARDS_ENABLED=true`
  - `MODULE_GUARD_ROLLOUT=supplier_management,process_digitization,traceability,public_trace`
- Run credentialed browser UAT for locked-route activation request + admin queue cleanup.
- Run authenticated admin API smoke for `POST /auth/admin/module-activation-requests/escalate-overdue`.

## Evidence

- Pre-migration backup: `/home/user/Documents/backups/aminra/pre-module-activation-escalation-deploy-20260921-112341/postgres.sql`
- Phase gate/deploy log dir: `/home/user/Documents/aminra-docker-system/docs/qa/20260921-112341-module-activation-escalation-runtime-deploy/`
- Browser UAT PASS: `browser-uat-scoped-guards/report.md`
- Escalation API smoke PASS: `escalation-api-smoke/report.md`
- Schema check: `schema-046-columns.txt`
- Fatal log scan: `recent-service-logs-final.txt`

## Key Results

- Backend focused container tests: `36 passed`.
- Frontend focused tests: `13 passed`.
- Frontend lint: PASS.
- Docker BuildKit probe: PASS.
- Backend image built: `sha256:ef9409f01357ad7cff025b7ce55b0844a14582260433d8bf7fcb73dd7fc1ef9b`.
- Frontend image built: `sha256:aa7dbb677e60c6c47dce8d048a11a61d174653fc6c8b0c745095224210548dbc`.
- Alembic current after explicit runtime upgrade: `046_module_activation_escal (head)`.
- Schema columns present:
  - `assigned_operator_id uuid`
  - `escalation_count integer NOT NULL DEFAULT 0`
  - `last_escalated_at timestamptz`
- Backend/frontend containers healthy after recreate.
- Local health: backend OK, frontend `/health` HTTP `200`.
- Public smoke during phase gate: `aminra.org` HTTP `200`, `/business/login` HTTP `200`.
- Stability loop: `4/4` healthy.
- Final fatal-log scan: PASS.
- Browser UAT with scoped guards: PASS (`CREDENTIALS`, `RUNTIME-BACKEND`, `RUNTIME-FRONTEND`, `BROWSER-UAT`).
- Escalation API smoke: PASS:
  - Created synthetic `process_digitization` activation request.
  - Marked only that request overdue.
  - Escalated via admin endpoint.
  - Observed `priority=urgent`, `escalation_count=1`, `last_escalated_at` present, assignee present.
  - Rejected synthetic request for cleanup.

## Important Notes

- First browser UAT attempt failed because runtime backend had `MODULE_GUARDS_ENABLED=false`; API correctly returned `200` for disabled process route, while the test expected fail-closed `403`. This was an environment/gate mismatch, not a product-code regression.
- Recreated backend with scoped guards enabled and reran; browser UAT passed.
- `scripts/automation/modularization-phase-gate.sh` initially ran migration before the rebuilt backend image exposed migration `046`; explicit post-recreate `./scripts/db-migrate.sh upgrade head` applied `046` correctly. Current runtime DB is now at head.
- Credentials/tokens were sourced from gitignored QA env and were not written to evidence.

## Remaining Risks

- Runtime scoped guard env was set via compose command invocation; if operators run compose later without these env values, backend may revert to `MODULE_GUARDS_ENABLED=false` depending on `.env`.
- Escalation notification is still in-app DB notification only; no confirmed email/Telegram/Slack/on-call fanout.
- Repo has untracked QA evidence directory; no commit/push was performed.
- Existing Sentry/Next deprecation warnings and frontend npm audit findings remain separate backlog.
