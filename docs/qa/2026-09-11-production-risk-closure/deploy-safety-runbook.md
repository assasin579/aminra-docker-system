# AMINRA deploy safety runbook — P1.1

Date: 2026-09-12

## Decision

The current Docker Compose topology is **not zero-downtime** for backend deploys. The verified chaos drill showed single-container backend force-recreate caused 10 read timeouts out of 429 public-trace requests.

Until AMINRA runs behind a real rolling/blue-green orchestrator, pilot/production deploys must be treated as a maintenance-window operation.

## Enforced guard

`scripts/deploy-from-registry.sh` now fails closed unless the deploy operator explicitly selects a safe strategy:

```bash
# Allowed only when downtime window is approved:
DEPLOY_STRATEGY=maintenance DEPLOY_WINDOW_APPROVED=true ./scripts/deploy-from-registry.sh <tag>

# Dry-run the gate without pulling/recreating:
DEPLOY_STRATEGY=maintenance DEPLOY_WINDOW_APPROVED=true DRY_RUN=true ./scripts/deploy-from-registry.sh <tag>
```

The script rejects:

```bash
./scripts/deploy-from-registry.sh <tag>
DEPLOY_STRATEGY=rolling ./scripts/deploy-from-registry.sh <tag>
```

Reason: Docker Compose `up -d` / force-recreate in this repository does not prove overlap + health-gated cutover. Claiming rolling from this script would be unsafe.

## Requirements for a future zero-downtime path

A valid rolling/blue-green implementation must prove all of:

1. At least two backend instances are live before draining the old one.
2. New instance passes `/health` with database and Qdrant connected before traffic cutover.
3. Traffic router/load balancer removes only the old unhealthy/draining instance.
4. In-flight requests are allowed to complete or are safely retried by the client/proxy.
5. Public trace burst test during deploy has 0 errors/timeouts.
6. Rollback path is health-gated and tested.

## Current release verdict impact

- Sandbox/demo: OK.
- Supervised pilot: acceptable only with a declared maintenance window or a separate rolling/blue-green implementation.
- Production/customer onboarding: blocked until a zero-downtime deploy path exists or the business accepts maintenance-window downtime.
