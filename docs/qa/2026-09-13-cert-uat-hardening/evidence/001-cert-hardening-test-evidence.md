# Certificate UAT hardening evidence

Date: 2026-09-13

## Changes verified

- Revoked certificates are terminal: status flip back to `active` is blocked with 409 and state remains revoked.
- Certificate issuance now writes required `halal_certificates.submission_id` and uses canonical local provider id for `issued_by` FK.
- Protected PDF download now enriches Keycloak claims before authorization, so live business token can download its own issued cert PDF.
- Added live UAT for provider issue → business PDF download → public verify, using real Keycloak tokens and live HTTP routes.

## Test evidence

Backend focused suite:

```text
collected 61 items
...
tests/test_cert_lifecycle_unit.py ..........
tests/test_cert_lifecycle_integration.py ......
tests/test_certificate_lifecycle_scope.py ..
tests/test_submission_state_machine.py ...
tests/test_submission_document_lock.py ....
tests/test_certificate_number_concurrency.py .
tests/test_certificate_pdf_unit.py .................
tests/test_certificate_pdf_integration.py .....
tests/test_certificate_pdf_integrity_smoke.py .....
tests/test_public_verify_blockchain.py .......
tests/test_certificate_live_issue_uat.py .

61 passed in 3.88s
```

Frontend cert lifecycle guardrails:

```text
__tests__/certificates-status-guardrails.test.tsx: 2 passed
frontend/aminra-web/e2e/14-cuj-cert-lifecycle.spec.ts: 5 passed
```
