#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy][ERROR] %s\n' "$*" >&2
  exit 1
}

compose_id() {
  local service="$1"
  docker compose ps -q "$service" 2>/dev/null || true
}

started_at() {
  local service="$1"
  local cid
  cid="$(compose_id "$service")"
  if [[ -z "$cid" ]]; then
    printf 'missing\n'
    return 0
  fi
  docker inspect -f '{{.State.StartedAt}}' "$cid"
}

snapshot_started_at() {
  local file="$1"
  shift
  : > "$file"
  local service
  for service in "$@"; do
    printf '%s=%s\n' "$service" "$(started_at "$service")" >> "$file"
  done
}

assert_unchanged_started_at() {
  local before_file="$1"
  shift
  local service before after
  for service in "$@"; do
    before="$(grep -E "^${service}=" "$before_file" | sed "s/^${service}=//")"
    after="$(started_at "$service")"
    if [[ "$before" != "$after" ]]; then
      fail "service ${service} was restarted/recreated unexpectedly: before=${before} after=${after}"
    fi
  done
}

wait_healthy() {
  local service="$1"
  local attempts="${2:-60}"
  local cid health
  for _ in $(seq 1 "$attempts"); do
    cid="$(compose_id "$service")"
    if [[ -n "$cid" ]]; then
      health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || true)"
      if [[ "$health" == "healthy" || "$health" == "running" ]]; then
        log "${service} is ${health}"
        return 0
      fi
    fi
    sleep 2
  done
  docker compose ps "$service" >&2 || true
  docker compose logs --tail=120 "$service" >&2 || true
  fail "${service} did not become healthy"
}

http_status_no_redirect() {
  local url="$1"
  python3 - "$url" <<'PY'
import sys, urllib.request
url = sys.argv[1]
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
opener = urllib.request.build_opener(NoRedirect)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AMINRA deploy-smoke"})
try:
    with opener.open(req, timeout=10) as resp:
        print(resp.status, resp.headers.get("Location") or "")
except urllib.error.HTTPError as exc:
    print(exc.code, exc.headers.get("Location") or "")
PY
}

smoke_frontend() {
  log "smoke frontend local root/landing"
  local root landing public_root public_landing
  root="$(http_status_no_redirect 'http://127.0.0.1:3100/')"
  landing="$(http_status_no_redirect 'http://127.0.0.1:3100/landing')"
  [[ "$root" == "307 /landing" || "$root" == "308 /landing" ]] || fail "local / expected redirect to /landing, got: ${root}"
  [[ "$landing" == "200 " ]] || fail "local /landing expected 200, got: ${landing}"

  public_root="$(http_status_no_redirect 'https://aminra.org/')"
  public_landing="$(http_status_no_redirect 'https://aminra.org/landing')"
  [[ "$public_root" == "307 /landing" || "$public_root" == "308 /landing" ]] || fail "public / expected redirect to /landing, got: ${public_root}"
  [[ "$public_landing" == "200 " ]] || fail "public /landing expected 200, got: ${public_landing}"
}

smoke_backend() {
  log "smoke backend health"
  local status
  status="$(python3 - <<'PY'
import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=10) as resp:
        print(resp.status)
except Exception as exc:
    print(type(exc).__name__)
PY
)"
  [[ "$status" == "200" ]] || fail "backend health expected 200, got: ${status}"
}
