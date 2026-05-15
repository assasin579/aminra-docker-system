# AMINRA — solo-founder shortcuts.
#
#   make help                       List all targets
#   make preview doc=halal_policy   Render a doc_type to /tmp/<doc>.pdf and open
#   make style-guide                Re-render the design system kitchen sink
#   make lint-templates             Run the template token + structure linter
#   make visual-test                Run visual regression suite
#   make visual-baseline            Re-record baselines (after intentional design change)
#   make pre-commit-install         One-time hook installation

JWT_FILE ?= /tmp/jwt.txt
BACKEND_HOST ?= http://localhost:8100
FIXTURE_DIR := backend/tests/fixtures/pdf_render

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ── Templates / design system ────────────────────────────────────────────────

doc ?= company_profile
.PHONY: preview
preview: ## Render <doc>.pdf via API; usage: make preview doc=company_profile
	@test -f $(JWT_FILE) || { echo "Missing $(JWT_FILE) — run scripts/gen_test_jwt.sh"; exit 1; }
	@JWT="$$(cat $(JWT_FILE))" ; \
	BODY=$$(python3 -c "import json,sys; d=json.load(open('$(FIXTURE_DIR)/$(doc)/sample.json')); print(json.dumps({'data':d,'is_draft':True,'lang':'vi'}))") ; \
	curl -s -X POST $(BACKEND_HOST)/api/templates/$(doc)/render-pdf \
	  -H "Authorization: Bearer $$JWT" \
	  -H "Content-Type: application/json" \
	  -d "$$BODY" \
	  -o /tmp/$(doc).pdf -w "HTTP %{http_code} · %{size_download}B · %{time_total}s\n"
	@echo "→ /tmp/$(doc).pdf"
	@command -v xdg-open >/dev/null && xdg-open /tmp/$(doc).pdf || true

.PHONY: style-guide
style-guide: ## Render the kitchen-sink style guide (doc=_style_guide shortcut)
	@$(MAKE) preview doc=_style_guide

.PHONY: lint-templates
lint-templates: ## Run scripts/lint-templates.sh (token + structure rules)
	@bash scripts/lint-templates.sh

.PHONY: visual-test
visual-test: ## Run visual regression suite inside backend container
	@docker compose exec -T aminra-backend bash -c \
	  'cd /app && . /vault/secrets/env.sh && pytest tests/visual -v'

.PHONY: visual-baseline
visual-baseline: ## Re-record baseline PNGs (use after intentional redesign)
	@docker compose exec -T aminra-backend bash -c \
	  'cd /app && . /vault/secrets/env.sh && pytest tests/visual --update-baseline -v'
	@echo "→ copying baselines back to host…"
	@docker cp aminra-docker-system-aminra-backend-1:/app/tests/visual/baselines backend/tests/visual/

.PHONY: sync-templates
sync-templates: ## Hot-copy backend/templates_html + services + auth into running container
	@docker cp backend/templates_html aminra-docker-system-aminra-backend-1:/app/
	@docker cp backend/services/pdf_renderer.py aminra-docker-system-aminra-backend-1:/app/services/
	@docker cp backend/services/pdf_render_schemas.py aminra-docker-system-aminra-backend-1:/app/services/
	@docker cp backend/auth/pdf_render_router.py aminra-docker-system-aminra-backend-1:/app/auth/
	@echo "synced — restart not needed unless Python sources changed"

# ── Keycloak (auth — ADR-005 Phase 1) ────────────────────────────────────────

.PHONY: keycloak-up
keycloak-up: ## Start keycloak service (depends postgres-db healthy)
	@docker compose up -d keycloak
	@echo "Keycloak starting at http://localhost:8180 — wait ~60s for first boot"

.PHONY: keycloak-bootstrap
keycloak-bootstrap: ## Idempotent: realm + clients + roles
	@bash scripts/keycloak-bootstrap.sh

.PHONY: keycloak-mfa
keycloak-mfa: ## Configure conditional MFA flow (run after keycloak-bootstrap)
	@bash scripts/keycloak-configure-mfa.sh

.PHONY: keycloak-logs
keycloak-logs: ## Tail keycloak logs
	@docker compose logs -f keycloak

# ── Frontend dev/prod toggle (U19 — eliminate Turbopack mem leak) ────────────
#
# Two services compete on host port 3100:
#   - aminra-frontend       (prod build, Next.js standalone, no HMR, no leak)
#   - aminra-frontend-dev   (next dev + Turbopack, HMR on, leaks over time)
#
# Default convention post-2026-05-14: run prod (`make fe-prod`).
# Only switch to dev (`make fe-dev`) when actively editing FE this session.

.PHONY: fe-prod
fe-prod: ## FE prod build (no HMR, no Turbopack leak) — default
	@docker compose stop aminra-frontend-dev 2>/dev/null || true
	@docker compose up -d --build aminra-frontend
	@echo "→ FE prod at http://localhost:3100  (run 'make fe-dev' if editing FE)"

.PHONY: fe-dev
fe-dev: ## FE dev mode with HMR — USE ONLY when actively editing FE this session
	@docker compose stop aminra-frontend 2>/dev/null || true
	@docker compose --profile dev up -d aminra-frontend-dev
	@echo "→ FE dev at http://localhost:3100  (memory leaks over time — switch back with 'make fe-prod')"

.PHONY: fe-stop
fe-stop: ## Stop both FE services
	@docker compose stop aminra-frontend aminra-frontend-dev 2>/dev/null || true

.PHONY: fe-status
fe-status: ## Show which FE service is running + memory %
	@docker compose ps aminra-frontend aminra-frontend-dev 2>/dev/null | tail -n +1
	@echo
	@docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' aminra-frontend aminra-frontend-dev 2>/dev/null || true

# ── Pre-commit ───────────────────────────────────────────────────────────────

.PHONY: pre-commit-install
pre-commit-install: ## Install pre-commit hooks (one-time per clone)
	pip install --user pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg

.PHONY: pre-commit-run
pre-commit-run: ## Run all pre-commit hooks against the full repo
	pre-commit run --all-files
