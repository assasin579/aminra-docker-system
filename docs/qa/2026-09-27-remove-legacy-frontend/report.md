# Remove legacy frontend/brand surfaces from AMINRA system

Date: 2026-09-27
Branch: feat/cb-trust-core-rbac-decisions
Safety: approved P0/P1/P2 cleanup executed locally; code/vault commits performed separately; no push performed.

## Executive verdict

PASS for source cleanup, runtime cleanup, and local/public-domain verification scope.

Removed the legacy frontend/brand surfaces from active AMINRA system files:

- Deleted the legacy frontend workspace and lockfile from `frontend/`.
- Removed legacy/Saigoncert active KB seed documents from `backend/docs`.
- Removed legacy lines from `backend/docs/demo.txt`.
- Removed the old external origin from backend CORS defaults and Docker Compose runtime CORS.
- Removed the old external origin from Keycloak bootstrap redirect URIs and web origins.
- Hardened `scripts/keycloak-bootstrap.sh` so re-runs patch the existing `aminra-frontend` client with the current redirect/web-origin allowlist instead of preserving stale origins.
- Removed setup-script copy/output references for the old frontend.
- Renamed evaluator logger/title/referer defaults to AMINRA.
- Sanitized historical QA summary content and removed legacy raw QA evidence files that exposed the old brand token in paths/content.
- Updated project-brain/branding vault notes so filesystem scans no longer expose the old brand token.

## Source verification

PASS:

```text
1) tracked content grep for old brand tokens:
0 results

2) filesystem content/path grep for old brand tokens, excluding .git, across:
- /home/user/Documents/aminra-docker-system
- /home/user/Documents/all-docs
0 results

3) docker compose config --quiet:
PASS

4) bash -n scripts/keycloak-bootstrap.sh scripts/setup.sh:
PASS

5) python3 -m py_compile backend/app.py backend/pipeline/evaluate.py:
PASS

6) git diff --check:
PASS
```

## Runtime verification

PASS:

- Built affected backend-image scope with the existing backend image as local base because `aminra-backend-base:local` was absent:
  - `docker compose build --build-arg BACKEND_BASE_IMAGE=aminra-docker-system-aminra-backend:latest aminra-backend arq-worker`
- Recreated only affected runtime services:
  - `docker compose up -d --no-deps aminra-backend arq-worker`
- Backend health PASS:
  - `http://localhost:8100/health` returned `status=ok`, DB connected, Qdrant connected.
- Frontend root smoke PASS:
  - `http://localhost:3100/` returned `307` to `/landing`.
- Keycloak realm smoke PASS:
  - `.well-known/openid-configuration` returned issuer and authorization endpoint.
- Keycloak client patch PASS:
  - `aminra-frontend` client redirect/web origins contain only localhost/dev/AMINRA origins from the current allowlist.
  - old-token hits in `rootUrl`, `redirectUris`, `webOrigins`: `0`.
- CORS allow smoke PASS:
  - `Origin: https://aminra.org` receives `access-control-allow-origin: https://aminra.org`.
- CORS deny smoke PASS:
  - removed old origin receives HTTP `400` and no `access-control-allow-origin`.

Runtime image evidence after recreate:

```text
aminra-backend image sha256:35348b49d3ad2d79caf8a9a37ff745744acbfb7178e7e1f80496887a5fc2d6eb, started 2026-09-27T06:56:33Z, healthy
arq-worker image sha256:0cdab5840147de669412df1447be366ec3023808b58c652ee3917d3f57998be0, started 2026-09-27T06:57:07Z
aminra-frontend unchanged and healthy
keycloak unchanged and healthy; client config patched through Admin REST
postgres/qdrant/redis unchanged and healthy
```

## Public-domain / infra verification

PASS for observable/local-controlled scope:

- DNS check for the removed old host returned no address records from this machine.
- HTTP and HTTPS checks failed at DNS resolution (`Could not resolve host`), so no public route was reachable.
- Targeted local infra config scan found no old-token hits under:
  - `/home/user/.cloudflared`
  - `/home/user/.config/cloudflared`
  - `/home/user/Documents/aminra-docker-system/nginx`
  - `/home/user/Documents/aminra-docker-system/.cloudflared`
  - `/etc/cloudflared`

Boundary: Cloudflared is running with token-based remote-managed configuration. Local files do not expose the remote tunnel ingress rules, so remote Cloudflare dashboard/API state was not mutated here. Observable DNS/HTTP result is clean.

## Verdict boundaries

- Source cleanup: PASS.
- Runtime cleanup: PASS for affected local Docker services and Keycloak client allowlist.
- Production/public-domain cleanup: PASS for observable DNS/HTTP and targeted local config scope; remote Cloudflare dashboard state not directly mutated because no local credentials/config were available.
- Push: NOT RUN.
