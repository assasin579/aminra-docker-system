#!/usr/bin/env bash
# Guard against the KC-sub vs AMINRA-id class bug.
#
# Under Keycloak SSO, `user["sub"]` (and owner["sub"] / jwt_user["sub"]) is
# the Keycloak user UUID, NOT the AMINRA `users.id` PG UUID. Passing it
# straight into any DB column that's FK-constrained on `users.id` either
# 500s on insert (FK violation) or silently mis-targets rows on
# read/update.
#
# The canonical fix is `await resolve_canonical_user_id(user, db)` from
# `backend/auth/identity.py`.
#
# This hook scans the STAGED ADDITIONS in the commit (not the whole file)
# and fails when a new `user["sub"]`-class read appears without an inline
# `# kc-sub: <reason>` annotation. Pre-existing usages are not blocked —
# the goal is to keep the class bug from spreading.
#
# Allowed reasons (informational only; the comment itself is the gate):
#   resolved-elsewhere  — handler later passes through resolve_canonical_user_id
#   compare-only        — used in a WHERE / equality check, not an FK write
#   logging-only        — passes to a log line, never reaches SQL
#   audit-meta          — recorded in audit_logs metadata JSON, not user_id col
#   intentional         — author has read identity.py and chose this path

set -euo pipefail

FILES=("$@")
if [ ${#FILES[@]} -eq 0 ]; then
  exit 0
fi

PATTERN='(user|owner|member|admin|jwt_user|biz|prov|auditor)\[("|'"'"')sub("|'"'"')\]|(user|owner|member|admin|jwt_user)\.get\(("|'"'"')sub("|'"'"')\)'

# Resolve a base ref for the diff. In a pre-commit context, the index has
# staged changes; compare against HEAD. For first-commit / detached cases,
# fall back to scanning the whole file (cautious default).
BASE_REF="HEAD"
if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  BASE_REF=""
fi

FAIL=0
for f in "${FILES[@]}"; do
  case "$f" in
    backend/auth/identity.py) continue;;        # the helper itself
    backend/tests/*|*/tests/*) continue;;       # tests can use mock subs
    scripts/check-user-sub-usage.sh) continue;; # this guard's own pattern
    *.py) ;;
    *) continue;;
  esac
  [ -f "$f" ] || continue

  if [ -n "$BASE_REF" ]; then
    # New lines staged in this commit only
    added=$(git diff --cached -U0 -- "$f" 2>/dev/null | awk '
      /^@@/ { in_hunk=1; next }
      in_hunk && /^\+[^+]/ { print substr($0, 2) }
    ')
  else
    added=$(cat "$f")
  fi

  [ -z "$added" ] && continue

  while IFS= read -r line; do
    # Skip lines with the bypass annotation
    if echo "$line" | grep -qE '#\s*kc-sub:'; then continue; fi
    # Skip comment-only lines
    if echo "$line" | grep -qE '^[[:space:]]*#'; then continue; fi
    # Skip log lines (best-effort)
    if echo "$line" | grep -qE 'log\.(info|debug|warning|error|exception)\('; then continue; fi
    echo "$f: $line"
    echo '  ↑ NEW use of Keycloak `sub` claim. If this writes to a FK→users.id column, use' >&2
    echo '    `await resolve_canonical_user_id(user, db)` from auth/identity.py.' >&2
    echo '    Otherwise add `# kc-sub: <reason>` on the line to acknowledge.' >&2
    FAIL=1
  done < <(echo "$added" | grep -E "$PATTERN" || true)
done

exit $FAIL
