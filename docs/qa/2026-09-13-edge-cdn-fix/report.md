# Public Edge/CDN Trace SLO Report — 2026-09-13

## Executive verdict

**PARTIAL / BLOCKED.** Local backend and local frontend proxy pass the SLO, but the public Cloudflare/tunnel path still fails p95 `<800ms` and remains `cf-cache-status: DYNAMIC`.

## Latest SLO rerun

Evidence: `evidence/004-public-trace-slo-rerun-before-edge-access.txt`

- local backend: `120/120` HTTP 200, p95 `419.7ms` — PASS
- local frontend proxy: `120/120` HTTP 200, p95 `427.3ms` — PASS
- public frontend proxy: `120/120` HTTP 200, p95 `957.8ms` — FAIL
- public cache status: `cf-cache-status: DYNAMIC`
- app proxy cache: `x-aminra-proxy-cache: hit`

## Diagnosis

The backend and app proxy are not the bottleneck in the latest run. Payload is only `1467` bytes and local proxy cache hits are fast. The remaining failure is public edge/tunnel/CDN behavior: Cloudflare is not caching the API path by default.

## Action taken

Created reusable Cloudflare rule script:

- `scripts/qa/apply-cloudflare-public-trace-cache-rule.sh`

The rule targets only:

```text
GET https://dev-web.silvergem.org/api/api/supply-chain/batches/trace/*
```

and applies short edge/browser TTLs for sealed public trace JSON.

## Blocker

Cloudflare credentials/config are not available in the repo/session:

- no `CLOUDFLARE_API_TOKEN`
- no `CLOUDFLARE_ZONE_ID`
- no Terraform/wrangler/Cloudflare config found

Evidence: `evidence/005-cloudflare-edge-ownership-discovery.txt` and `evidence/007-cloudflare-cache-rule-apply-attempt.txt`.

## Required next step

Provide Cloudflare API token + zone ID, or apply the equivalent cache rule manually in Cloudflare, then rerun the public SLO. Until then, production/public QR load-readiness remains blocked.
