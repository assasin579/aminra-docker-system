# Branch Protection — Audit & Recommendations (2026-04-29)

**Repo**: `assasin579/aminra-docker-system`
**Default branch**: `main`
**Collaborators**: 1 (solo dev — `assasin579`)

---

## Current state

❌ **Main branch has NO protection.**
- Force push: allowed
- Direct push: allowed (no PR required)
- No required status checks
- No required reviews
- No linear history requirement
- Deletion: allowed

This is a critical Phase 0 gap per the engineering methodology.

---

## Existing CI workflows (status checks available to require)

| Workflow file | Job name | Trigger |
|---|---|---|
| `.github/workflows/ci.yml` | `CI / lint-and-smoke` (or similar) | PR + push |
| `.github/workflows/test.yml` | `Test & Coverage` | PR + push |
| `.github/workflows/build-push.yml` | `Build & Push Images` | push main, tags |
| `.github/workflows/deploy.yml` | `Deploy` | workflow_run |
| `.github/workflows/security-scan.yml` (NEW Day 2) | `python-security`, `node-security`, `gitleaks`, `semgrep`, `security-gate` | PR + push + cron |

**Recent runs on main:**
- ❌ `Build & Push Images` — failing (pre-existing, needs investigation)
- ❌ `Test & Coverage` — failing (pre-existing, needs investigation)
- ⏭ `Deploy` — skipped (waits on build)

→ **Action**: investigate failing workflows BEFORE enabling required-status-checks rule (else even own PRs would block).

---

## Recommended settings for solo dev

Trade-off: strict rules vs solo workflow friction. Below balances safety with usability.

### Tier A — apply immediately (low friction, high safety)
- ✅ **Block force push** (`allow_force_pushes: false`) — catches accidental history rewrites
- ✅ **Block branch deletion** (`allow_deletions: false`)
- ✅ **Require linear history** (`required_linear_history: true`) — keeps log readable
- ✅ **Require branches up to date before merge** (`require_branches_to_be_up_to_date: true`)

### Tier B — apply after fixing failing workflows
- ✅ **Required status checks**: `CI`, `Test & Coverage`, `python-security`, `node-security`, `gitleaks`, `semgrep`, `security-gate`
- ⚠ Pre-req: ensure all 4 currently-failing workflows are green on main first

### Tier C — apply when team grows beyond solo
- 🔵 **Require PR review** (`required_approving_review_count: 1`) — currently blocks solo dev unless GitHub allows self-approval (it does NOT by default)
- 🔵 **Dismiss stale reviews on push** (`dismiss_stale_reviews: true`)
- 🔵 **Require code owner review** (when CODEOWNERS file exists)

### Tier D — anti-pattern for solo, recommended for production
- 🔵 **Restrict who can push to main** (only via PR) — for solo this means solo dev creates their own PR for every change
- 🔵 **Require signed commits** (GPG/SSH signed)

---

## Proposed apply (Tier A only — safe for solo)

```bash
REPO="assasin579/aminra-docker-system"

gh api -X PUT repos/$REPO/branches/main/protection \
  --field 'required_status_checks=null' \
  --field 'enforce_admins=false' \
  --field 'required_pull_request_reviews=null' \
  --field 'restrictions=null' \
  --field 'required_linear_history=true' \
  --field 'allow_force_pushes=false' \
  --field 'allow_deletions=false' \
  --field 'block_creations=false' \
  --field 'required_conversation_resolution=true'
```

After Tier B (failing workflows fixed):

```bash
gh api -X PATCH repos/$REPO/branches/main/protection \
  --field 'required_status_checks={"strict":true,"contexts":["lint-and-smoke","test","python-security","node-security","gitleaks","semgrep","security-gate"]}'
```

(Replace context names with actual job names from workflow definitions; verify via `gh api repos/$REPO/actions/runs/<RUN_ID>/jobs --jq '.jobs[].name'`.)

---

## Decision required (user)

- [ ] Apply Tier A immediately?
- [ ] Investigate + fix failing `ci.yml` and `test.yml` runs on main → then apply Tier B?
- [ ] Defer Tier C (review requirement) until team grows?
- [ ] Defer Tier D (signed commits, restrict push)?

I will NOT apply branch protection changes without explicit confirmation — this affects shared GitHub state.
