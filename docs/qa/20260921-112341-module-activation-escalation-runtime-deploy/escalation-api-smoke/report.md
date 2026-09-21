# AMINRA Module Activation Escalation — Authenticated API Smoke

Date: 2026-09-21T11:38:30.742538-04:00
Verdict: **PASS**

## Scope
- Create synthetic business request for `process_digitization`.
- Mark only that synthetic request overdue in sandbox DB.
- Call admin endpoint `POST /auth/admin/module-activation-requests/escalate-overdue`.
- Verify priority/escalation metadata, then reject request for cleanup.

## Evidence
- Status: `/home/user/Documents/aminra-docker-system/docs/qa/20260921-112341-module-activation-escalation-runtime-deploy/escalation-api-smoke/status.tsv`
- Response: `/home/user/Documents/aminra-docker-system/docs/qa/20260921-112341-module-activation-escalation-runtime-deploy/escalation-api-smoke/evidence/terminal/escalate-overdue-response-redacted.json`
- DB row: `/home/user/Documents/aminra-docker-system/docs/qa/20260921-112341-module-activation-escalation-runtime-deploy/escalation-api-smoke/evidence/terminal/post-escalation-db-row.txt`

## Credential Safety
Tokens/passwords were used from gitignored local QA env and never written to evidence.
