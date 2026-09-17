# AMINRA Gate 1 — Unsupervised Customer Onboarding Automated QA

Date: 2026-09-17T07:24:25-04:00
Public base URL: https://aminra.org
Evidence root: docs/qa/20260917-gate1-onboarding-final
Acceptance matrix: docs/qa/20260917-gate1-onboarding-final/acceptance-matrix.md
Status ledger: docs/qa/20260917-gate1-onboarding-final/status.tsv

## Automated verdict

- PASS rows: 11
- FAIL rows: 0
- WARN/BLOCKED/DEFERRED rows: 0

Final verdict rule:
- PASS only if every required P0/P1 Gate 1 automated row is PASS and full desktop Chromium has 0 failed.
- FAIL/NO-GO if any required Gate 1 row is FAIL.
- BLOCKED if email/credential/external dependency prevents verification.

## Gate mapping

- G1-RUNTIME: runtime health and public login availability.
- G1-EMAIL: live/canonical email verification and password-reset dependency checks.
- G1-SESSION: login, logout, Keycloak/OIDC, account-switch/session isolation.
- G1-BUSINESS: business first-value flow and supply-chain write contracts.
- G1-PROVIDER: provider/CB first-value certificate/authority flow.
- G1-AUDITOR: auditor/role-boundary backend smoke.
- G1-ERROR: invalid input and error UX regressions.
- G1-OUTPUT: public/demo artifact correctness.
- G1-FULL-CHROMIUM: full desktop browser regression matrix.

## Current recommendation

PASS candidate — review evidence and skipped tests before customer handoff.
