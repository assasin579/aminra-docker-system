#!/usr/bin/env bash
# lint-templates.sh — token + structure rules for backend/templates_html/
#
# Run via pre-commit (.pre-commit-config.yaml) and CI. Manual run:
#   bash scripts/lint-templates.sh
#
# Exits non-zero on first violation. Failures print file:line for fast fix.
#
# Why each rule (linked to docs/features/pdf-html-renderer/spec.md §6 + threat-model R3,R9):
# - Gate 1: doc-specific .css cấm raw hex — design tokens là single source of truth (L1/L2/L3)
# - Gate 2: font-* properties phải qua var(--*) — drift prevention
# - Gate 3: inline style cấm raw hex — same reason as Gate 1
# - Gate 4: external <link href> cấm — defense against supply-chain template hijack
# - Gate 5: <script> / <iframe> cấm — CSP + JS disabled at render, defense in depth
# - Gate 6: <img src=URL> raw cấm — SSRF defence (only asset() helper allowed)

set -euo pipefail

ROOT="${REPO_ROOT:-$(pwd)}/backend/templates_html"
EXIT=0

if [ ! -d "$ROOT" ]; then
  echo "lint-templates: template root $ROOT not found — skipping" >&2
  exit 0
fi

red()  { printf "\033[31m%s\033[0m\n" "$*"; }
green(){ printf "\033[32m%s\033[0m\n" "$*"; }

# ── Gate 1 — Doc-specific CSS cấm raw hex ──────────────────────────────────
v=$(grep -rEn "color\s*:\s*#[0-9a-fA-F]{3,8}" "$ROOT" --include="*.css" \
     | grep -v "_base/base.css" || true)
if [ -n "$v" ]; then
  red "❌ Gate 1: raw hex color in doc-specific CSS — must use var(--c-*):"
  echo "$v"; EXIT=1
fi

# ── Gate 2 — font-* properties phải qua var(--*) ───────────────────────────
v=$(grep -rEn "font-(size|family|weight)\s*:" "$ROOT" --include="*.css" \
     | grep -v "_base/base.css" \
     | grep -vE "var\(--|@font-face" || true)
if [ -n "$v" ]; then
  red "❌ Gate 2: raw font property — must use var(--fs-*) / var(--font-sans):"
  echo "$v"; EXIT=1
fi

# ── Gate 3 — inline style trong HTML cấm raw hex ──────────────────────────
v=$(grep -rEn 'style="[^"]*#[0-9a-fA-F]{3,8}' "$ROOT" --include="*.html" || true)
if [ -n "$v" ]; then
  red "❌ Gate 3: raw hex in inline style — move to base.css token:"
  echo "$v"; EXIT=1
fi

# ── Gate 4 — <link rel=stylesheet> chỉ allow asset() helper hoặc relative ─
v=$(grep -rEn '<link[^>]*rel="stylesheet"[^>]*href="[^"]*"' "$ROOT" --include="*.html" \
     | grep -vE 'href="\{\{ asset\(' || true)
if [ -n "$v" ]; then
  red "❌ Gate 4: stylesheet href must use {{ asset(...) }} helper — found:"
  echo "$v"; EXIT=1
fi

# ── Gate 5 — <script> / <iframe> cấm trong template ───────────────────────
v=$(grep -rEn '<(script|iframe)[> ]' "$ROOT" --include="*.html" || true)
if [ -n "$v" ]; then
  red "❌ Gate 5: <script> / <iframe> tag forbidden in templates:"
  echo "$v"; EXIT=1
fi

# ── Gate 6 — <img src> raw URL cấm — only asset() ─────────────────────────
v=$(grep -rEn '<img[^>]*src="(http|//|/)' "$ROOT" --include="*.html" \
     | grep -vE 'src="\{\{ asset\(' || true)
if [ -n "$v" ]; then
  red "❌ Gate 6: <img src> must use {{ asset(...) }} helper — never raw URL:"
  echo "$v"; EXIT=1
fi

# ── Gate 7 — onclick/onload/etc inline event handlers cấm ─────────────────
v=$(grep -rEn ' on[a-z]+="' "$ROOT" --include="*.html" || true)
if [ -n "$v" ]; then
  red "❌ Gate 7: inline JS event handler forbidden (CSP blocks anyway):"
  echo "$v"; EXIT=1
fi

if [ $EXIT -eq 0 ]; then
  green "✓ templates_html lint clean"
fi
exit $EXIT
