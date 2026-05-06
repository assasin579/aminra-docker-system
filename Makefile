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

# ── Pre-commit ───────────────────────────────────────────────────────────────

.PHONY: pre-commit-install
pre-commit-install: ## Install pre-commit hooks (one-time per clone)
	pip install --user pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg

.PHONY: pre-commit-run
pre-commit-run: ## Run all pre-commit hooks against the full repo
	pre-commit run --all-files
