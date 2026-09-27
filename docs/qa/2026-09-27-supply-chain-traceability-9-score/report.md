# AMINRA Supply-chain / CB eligibility / traceability 9-score readiness evidence

Date: 2026-09-27
Agent lane: Supply-chain / CB eligibility / public trace / traceability
Branch observed: feat/cb-trust-core-rbac-decisions
Safety: no commit, no push, no deploy, no secrets printed. Targeted tests only.

## Scope inspected

Backend source/tests inspected:
- `backend/supply_chain/eligibility_service.py`
- `backend/supply_chain/supplier_router.py`
- `backend/supply_chain/batch_router.py`
- `backend/supply_chain/models.py`
- `backend/tests/test_supplier_eligibility_service.py`
- `backend/tests/test_supply_chain_supplier_eligibility_routes.py`
- `backend/tests/test_supply_chain_batches.py`
- `backend/tests/test_supply_chain_sealing.py`
- migrations `038_cb_supplier_certificate_eligibility.py`, `039_supplier_authority_batch_snapshot.py`, `040_public_trace_id.py`

## Score gaps found before this lane change

1. CB-authoritative supplier eligibility was mostly covered, including source-of-truth = `cb`, provider authority checks, source certificate linkage, takeover block, status fanout alerts, and business self-verification block.
2. Fail-closed material/batch selection was covered for missing, cross-tenant, revoked-at-create, revoked-at-seal, and snapshot-on-batch-material.
3. Public trace was covered for opaque UUID lookup, rejection of business batch code, sealed-only access, public_trace_enabled gate, duplicate tenant-local batch codes, and sealed snapshot rather than live table data.
4. Risk alert list/ack/resolve boundary was covered for tenant-owned alerts only.
5. Safe gap preventing a stronger 9/10: the API model did not reject inverted validity windows (`valid_until < valid_from`) until the database CHECK constraint. The database was safe, but API-layer fail-closed contract and evidence were missing. This is a source/test gap because eligibility upsert should fail before attempting any write.
6. Runtime public trace SLO/load evidence remains a residual gap unless a dedicated load gate is run against an approved target. Code has a short TTL public trace response cache (`PUBLIC_TRACE_CACHE_TTL_SECONDS`, default 5s) but this lane did not run a load/soak test.

## Change implemented

TDD closure for API-layer CB certificate date-window fail-closed behavior:

- Added a focused route/model contract test proving `SupplierCertificateEligibilityUpsert` rejects an inverted date window.
- Added Pydantic `model_validator(mode="after")` enforcing `valid_until >= valid_from` before router/database write.
- Database CHECK constraint remains the authoritative second-line guard.

## Commands run and evidence

1. Baseline attempted from host:

```bash
cd /home/user/Documents/aminra-docker-system/backend
pytest tests/test_supply_chain_supplier_eligibility_routes.py::test_supplier_eligibility_rejects_inverted_validity_window -q
```

Result: blocked by host environment: `pytest: command not found`.

2. Docker/container status discovery:

```bash
cd /home/user/Documents/aminra-docker-system
docker compose ps --format json
```

Result: stack was running; backend/frontend/postgres/qdrant/redis/keycloak healthy where applicable. No secrets printed.

3. Targeted single-test gate using backend image with host backend bind mount:

```bash
cd /home/user/Documents/aminra-docker-system
docker compose run --rm -T -v "$PWD/backend:/app" --entrypoint pytest aminra-backend \
  tests/test_supply_chain_supplier_eligibility_routes.py::test_supplier_eligibility_rejects_inverted_validity_window -q
```

Result: PASS

```text
collected 1 item
tests/test_supply_chain_supplier_eligibility_routes.py . [100%]
1 passed in 3.78s
```

Note: this first `docker compose run` unexpectedly recreated/started `postgres-db` and `qdrant-db` due Compose dependency behavior. No destructive cleanup, no manual restart/deploy was performed. Subsequent targeted gate used `--no-deps`.

4. Targeted supply-chain eligibility/traceability regression gate:

```bash
cd /home/user/Documents/aminra-docker-system
docker compose run --rm -T --no-deps -v "$PWD/backend:/app" --entrypoint pytest aminra-backend \
  tests/test_supplier_eligibility_service.py \
  tests/test_supply_chain_supplier_eligibility_routes.py \
  tests/test_supply_chain_sealing.py -q
```

Result: PASS

```text
collected 51 items
tests/test_supplier_eligibility_service.py .............                 [ 25%]
tests/test_supply_chain_supplier_eligibility_routes.py ............      [ 49%]
tests/test_supply_chain_sealing.py ...................s......            [100%]
50 passed, 1 skipped in 37.46s
```

5. Diff/status inspection:

```bash
cd /home/user/Documents/aminra-docker-system
git diff -- backend/supply_chain/models.py backend/tests/test_supply_chain_supplier_eligibility_routes.py && git status --short
```

Result: confirmed only this lane's intended files changed by this agent; repo also contained unrelated pre-existing/parallel modifications from other lanes.

## Readiness assessment after this lane

Supply-chain / CB eligibility / traceability is closer to 9/10 because evidence now covers:

- CB-authoritative eligibility: provider-only upsert, source certificate authority, source_of_truth = cb, takeover block, active/current scope filtering.
- Fail-closed material/batch selection: missing/cross-tenant material rejected, non-CB/revoked/expired/future/out-of-scope suppliers excluded, recheck at create and at seal.
- Sealed public trace: opaque public_trace_id, disabled-by-default before seal, business batch code rejected, sealed snapshot used instead of live mutable fields, duplicate tenant-local batch codes isolated by UUID trace id.
- Risk alerts: revoked/suspended/expired transitions fan out to active impacted buyers; business lists and updates only own alerts.
- New gap closed: inverted validity windows rejected at API model boundary before DB write.

## Residual risks / not claimed

- Runtime public trace SLO/load evidence was not executed in this lane. Recommended safe plan: run a bounded k6/Locust profile against a seeded public trace fixture with 70% valid public trace, 10% invalid public trace, 10% authenticated business supply-chain reads, 5% provider cert/risk reads, 5% writes blocked to staging only. Thresholds from existing plan: public trace p95 < 800 ms at 50 concurrent public readers; authenticated dashboard/API p95 < 1200 ms at 20 concurrent users.
- One sealing test remains intentionally skipped for assigned-member seal in unit context because `check_permission_db` non-owner branch depends on a global asyncpg pool not initialized in that unit test context. Existing note says live HTTP integration covers this path; this lane did not broaden it.
- Public trace cache is intentionally short-lived (default 5s). If operations require immediate revocation visibility after disabling public_trace_enabled, either set `PUBLIC_TRACE_CACHE_TTL_SECONDS=0` for that environment or add an explicit cache invalidation path.
- I did not run full frontend/browser evidence because backend remains authoritative and this lane changed only backend model/test contract.

## Exact next step

Run a safe staging-only public trace SLO gate with seeded valid/invalid trace IDs and archive the raw results under this same QA directory. Do not run destructive chaos or broad package upgrades.
