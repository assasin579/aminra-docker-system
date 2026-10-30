# ADR-009 — main source authority; CI/CD deferred

Status: Accepted by owner 2026-10-30; narrowed by the owner's later direction to clean branches and a clear Git workflow. Automated CI/CD implementation is deferred.

## 1. Analysis

Main historically lagged serving source. Local production/feature pointers were ambiguous and the primary checkout contained unrelated WIP. The owner approved reconciling verified application source onto main without importing the unrelated release ancestry.

## 2. Solution

Use main as the canonical reviewed source, with short-lived feat/*, fix/* and docs/* branches entering through PRs and manual evidence. Preserve work in dedicated worktrees. Main requires PRs, conversation resolution and linear history; force pushes/deletion are prohibited. Single-owner external approval count remains zero. No automated check names block merges while CI is deferred. Version tags identify separately approved releases and cannot be rewritten.

GitHub workflows remain disabled. Their existing files are preserved unchanged, avoiding accidental CI/CD publication or a need for workflow credential scope. The unpublished automation proposal is retained on a local archive branch, not main. A merge does not deploy, migrate or approve pilot use.

## 3. Risks

Manual test/review discipline is required. Existing runtime images remain independently identified; main is not assumed identical to an image merely because it is the newest branch. Preserve historical migration ancestry and exclude undeployed proposal code. Independent pilot, certificate, SMTP, device, recovery and retention gates remain open.

## 4. Tests

Source integration uses the recorded manual backend/FE tests, builds, source hashes and live read-only preflight. Subsequent changes must provide scoped evidence in their PR. CI/CD helper tests belong to the archived proposal and are not active release gates.

## 5. Improvements

See [Git workflow](../../operations/git-workflow.md). Revisit automation in a separate owner-authorized task; choose its checks and deployment controls at that time rather than freezing main on nonexistent CI results.
