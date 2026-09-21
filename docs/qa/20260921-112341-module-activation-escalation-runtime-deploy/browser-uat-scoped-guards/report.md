# AMINRA Module Activation Request — Credentialed Browser UAT

Date: 2026-09-21T11:36:27-04:00
Repo: /home/user/Documents/aminra-docker-system
Verdict: **GO for local sandbox credentialed browser UAT**

## Scope / Acceptance Criteria

- business locked-route CTA creates request
- admin queue shows SLA/notification cues
- admin rejects QA request for cleanup
- QA credentials are sourced from gitignored local env only; secret values are never printed

## Evidence

- Status: /home/user/Documents/aminra-docker-system/docs/qa/20260921-112341-module-activation-escalation-runtime-deploy/browser-uat-scoped-guards/status.tsv
- Redacted env shape: /home/user/Documents/aminra-docker-system/docs/qa/20260921-112341-module-activation-escalation-runtime-deploy/browser-uat-scoped-guards/evidence/terminal/effective-env-redacted.txt
- Playwright log: /home/user/Documents/aminra-docker-system/docs/qa/20260921-112341-module-activation-escalation-runtime-deploy/browser-uat-scoped-guards/evidence/terminal/playwright-module-activation.txt
- Screenshots: /home/user/Documents/aminra-docker-system/docs/qa/20260921-112341-module-activation-escalation-runtime-deploy/browser-uat-scoped-guards/evidence/

## Credential Safety

Credential values are intentionally **REDACTED**. The runner sources .env and .qa/aminra-demo-credentials.env; if required QA keys are missing, it runs scripts/qa/repair-demo-accounts.sh which writes mode-600 gitignored credentials.
