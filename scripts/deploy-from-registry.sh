#!/bin/bash
set -euo pipefail

# ── Deploy from GHCR ─────────────────────────────────────────────────────────
# Usage:
#   ./scripts/deploy-from-registry.sh                  # deploy latest
#   ./scripts/deploy-from-registry.sh abc1234          # deploy specific tag
#   ./scripts/deploy-from-registry.sh v1.2.0           # deploy version tag

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

TAG="${1:-latest}"
GITHUB_OWNER="${GITHUB_OWNER:-aminra-dev}"
REGISTRY="ghcr.io"
DEPLOY_STRATEGY="${DEPLOY_STRATEGY:-}"
DEPLOY_WINDOW_APPROVED="${DEPLOY_WINDOW_APPROVED:-false}"
DRY_RUN="${DRY_RUN:-false}"

cat <<'EOF'
==> AMINRA deploy safety gate
    Docker Compose force-recreate is not zero-downtime for the current single-backend topology.
    Production/pilot deploys must use one of:
      DEPLOY_STRATEGY=maintenance DEPLOY_WINDOW_APPROVED=true  # explicit downtime window
      DEPLOY_STRATEGY=rolling                                  # external rolling/blue-green orchestrator only
EOF

case "$DEPLOY_STRATEGY" in
  maintenance)
    if [ "$DEPLOY_WINDOW_APPROVED" != "true" ]; then
      echo "ERROR: maintenance deploy requires DEPLOY_WINDOW_APPROVED=true" >&2
      exit 64
    fi
    ;;
  rolling)
    echo "ERROR: rolling/blue-green is not implemented by this Docker Compose script; use an orchestrator/runbook that proves overlap + health-gated cutover." >&2
    exit 65
    ;;
  *)
    echo "ERROR: set DEPLOY_STRATEGY=maintenance with an approved window, or use an external rolling/blue-green deploy path." >&2
    exit 64
    ;;
esac

if [ "$DRY_RUN" = "true" ]; then
  echo "==> DRY_RUN passed deploy safety gate for tag: ${TAG}"
  exit 0
fi

echo "==> Deploying tag: ${TAG}"
echo "==> Strategy: ${DEPLOY_STRATEGY}"
echo "==> Registry: ${REGISTRY}/${GITHUB_OWNER}/aminra-*"

# Save current tag for rollback
PREV_TAG=$(cat .deploy-tag 2>/dev/null || echo "none")
echo "$TAG" > .deploy-tag

# Login to GHCR (if not already)
if ! docker pull "${REGISTRY}/${GITHUB_OWNER}/aminra-backend:${TAG}" 2>/dev/null; then
    echo "==> Login to GHCR required"
    echo "    Run: echo \$GITHUB_TOKEN | docker login ghcr.io -u \$GITHUB_USER --password-stdin"
    exit 1
fi

echo "==> Pulling images..."
docker pull "${REGISTRY}/${GITHUB_OWNER}/aminra-backend:${TAG}"
docker pull "${REGISTRY}/${GITHUB_OWNER}/aminra-frontend:${TAG}"

echo "==> Starting services..."
IMAGE_TAG="$TAG" GITHUB_OWNER="$GITHUB_OWNER" \
    docker compose -f docker-compose.yml -f docker-compose.registry.yml up -d

echo "==> Waiting for health..."
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8100/health > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    sleep 5
done

if [ "$HEALTHY" = "false" ]; then
    echo "==> FAILED! Rolling back to ${PREV_TAG}..."
    if [ "$PREV_TAG" != "none" ]; then
        IMAGE_TAG="$PREV_TAG" GITHUB_OWNER="$GITHUB_OWNER" \
            docker compose -f docker-compose.yml -f docker-compose.registry.yml up -d
        echo "$PREV_TAG" > .deploy-tag
    fi
    exit 1
fi

echo ""
echo "==> Deployed successfully"
echo "    Tag:      ${TAG}"
echo "    Backend:  $(curl -sf http://localhost:8100/health)"
echo "    Frontend: $(curl -sf -o /dev/null -w 'HTTP %{http_code}' http://localhost:3100)"
