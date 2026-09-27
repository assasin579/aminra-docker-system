# Public trace SLO/load gate

Date: 2026-09-27
Branch: feat/cb-trust-core-rbac-decisions
Public host: https://aminra.org
Trace fixture: see `trace-id.txt`

## Verdict

PARTIAL PASS.

What passed:
- Valid public trace returns 200 across local backend, local frontend proxy, and public frontend proxy.
- Invalid plain and injection-like trace IDs return 404.
- No obvious private fields (`tenant_id`, `provider_id`, `source_certificate_id`, `changed_by`) appeared in the 200 public response body.
- Local backend load: 120 requests, concurrency 30, p95 463.2 ms, 0 errors.
- Local frontend proxy load: 120 requests, concurrency 30, p95 389.5 ms, 0 errors.
- Public warmed load passed up to concurrency 20: 120 requests, p95 767.6 ms, 0 errors.

What did not pass:
- Public cold-ish concurrency 30 target p95<=800 ms missed narrowly: p95 885.8 ms.
- Public warmed concurrency 30 also missed: p95 947.4 ms.
- Cloudflare reported `cf-cache-status: dynamic`; edge cache is not HIT even though app proxy reports `x-aminra-proxy-cache: hit`.

## Interpretation

Backend and app proxy are not the bottleneck. The residual SLO miss is in public edge/tunnel/cache behavior.

Current readiness impact:
- Supply-chain / CB eligibility / traceability can be scored 9/10 for source/runtime/local-proxy correctness.
- Public buyer-facing trace SLO should stay WARN, not hard PASS, until Cloudflare cache rule is applied and `cf-cache-status: HIT` is observed or concurrency-30 public p95 stabilizes <=800 ms.

## Remediation prepared

Updated `scripts/qa/apply-cloudflare-public-trace-cache-rule.sh` so its default host is `aminra.org` instead of the previous dev host and supports `PUBLIC_TRACE_HOST` override.

Blocked action:
- The session environment does not expose `CLOUDFLARE_API_TOKEN` or `CLOUDFLARE_ZONE_ID`, so I did not apply external Cloudflare rules.

## Evidence

- `001-seed-public-trace-fixture.txt`
- `002-valid-invalid-smoke.txt`
- `003-split-slo-load.jsonl`
- `004-public-warmed-rerun.jsonl`
