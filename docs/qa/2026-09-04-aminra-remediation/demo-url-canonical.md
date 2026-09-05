# AMINRA Demo URL Canonical Decision — 2026-09-04

## Decision

Use these URLs for controlled sandbox demo:

- Local operator demo: `http://localhost:3100`
- Public sandbox demo: `https://dev-web.silvergem.org`

Do **not** use `https://fe.silvergem.org` for AMINRA demo scripts, sales walkthroughs, or release gates until the hostname/tunnel ownership is fixed and explicitly re-promoted.

## Rationale

- `dev-web.silvergem.org` passes the runtime smoke path.
- `fe.silvergem.org` is a known 502/hostname-drift path from the 2026-09-04 QA pass.
- A canonical URL prevents demo prep from mixing a working sandbox endpoint with a legacy/public hostname that fails for reasons unrelated to current AMINRA app readiness.

## Verification rule

- Default smoke/public URL must stay `https://dev-web.silvergem.org`.
- `fe.silvergem.org` may be tested only by explicit override, e.g. `AMINRA_SMOKE_PUBLIC_URLS='https://dev-web.silvergem.org https://fe.silvergem.org' bash scripts/qa/runtime-smoke.sh`, and failures there are hostname-drift evidence, not canonical demo failure.
