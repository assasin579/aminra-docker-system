# SMTP / VerifyEmail Live-Send QA Report — 2026-09-13

## Executive verdict

**Sandbox/customer-onboarding SMTP mechanics: PASS for QA internal relay.**

Keycloak `verifyEmail` was enabled, realm SMTP was pointed at a local Docker-network QA capture relay, `execute-actions-email` for `VERIFY_EMAIL` was accepted, and the email was captured with `SMTP_CAPTURE_BEGIN`/`SMTP_CAPTURE_END`.

## Evidence

- SMTP capture relay restart: `evidence/005-smtp-capture-restart.txt`
- Keycloak live-send trigger: `evidence/006-keycloak-verify-email-live-send-capture.txt`
- Captured email proof: `evidence/007-smtp-capture-after-trigger.txt`
- Customer-onboarding SMTP config gate: `evidence/009-customer-onboarding-smtp-gate-final.txt`

## Result

- `verifyEmail`: enabled
- `resetPasswordAllowed`: enabled
- SMTP host/from/port: configured for QA relay
- Live-send: captured recipient + Verify Email action body
- Gate mode: `QA_ALLOW_INSECURE_SMTP=1`

## Residual blocker

This is **not production SMTP readiness**. Production still requires real provider config with TLS/auth and domain alignment (SPF/DKIM/DMARC). The QA relay is intentionally unauthenticated and non-TLS because it is internal-only.
