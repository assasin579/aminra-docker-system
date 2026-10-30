# AMINRA Git workflow

## 1. Analysis

Main is the canonical reviewed source. CI/CD is deferred by owner direction on 2026-10-30. A merge is a source-control action; it does not deploy or change the database.

## 2. Solution

| Branch | Purpose | Lifetime |
|---|---|---|
| main | Clean, reviewed integration source | Permanent |
| feat/<topic> | One feature from current main | Until merged |
| fix/<topic> | One bug fix from current main | Until merged |
| docs/<topic> | Documentation changes | Until merged |
| release/<version-or-date> | Optional stabilization or verified deployment checkpoint | Retain while needed |
| wip/* | Local work preserved for later review; never assume release-ready | Until reconciled |
| archive/* | Historical/proposed work; no deployment authority | Retained reference |

Routine work:

1. Start from clean main: `git switch main`, then `git pull --ff-only`.
2. Create a focused branch: `git switch -c fix/<topic>` (or feat/docs).
3. Review the diff, run checks appropriate to the affected behavior, and record exact results in the PR. Include API/browser/DB checks when that behavior changes; do not infer acceptance from test totals.
4. Commit logical changes and push the topic branch. Open a PR to main. Review scope, source and migration impact, then squash-merge after manual validation. Main requires a PR, conversation resolution, linear history, and prohibits force push/deletion. There are no required automated check names while CI is deferred.
5. After merge, update local main with `git pull --ff-only`. Delete merged topic branches only when no worktree or WIP depends on them. Keep historical deployment checkpoints until their replacement is established.
6. Release/deploy is a separate, explicitly requested task. Record the source commit and exact FE/BE image IDs plus schema; tag approved releases as vX.Y.Z[-rc.N] without rewriting published tags. Do not deploy automatically after a merge.

Do not use `git pull` with an implicit merge to reconcile a diverged feature branch. Review its unique commits against main; migrate the intended changes in a new topic branch. Preserve WIP before switching source baselines. Never commit node_modules, generated builds, credentials, private container config or database dumps.

## 3. Risks

The old `production` branch is a historical local pointer, not the running deployment identity. The primary old feature branch and temporary worktrees contain unrelated work; do not merge them wholesale. CI/CD drafts live only on local archive/ci-cd-draft-20261030 and are not part of main. Legacy GitHub workflow files are retained unchanged for history and are disabled remotely until a separately approved CI/CD task.

Source reconciliation excludes the undeployed attachment migration 055 and its unused modules. The existing schema source has two branches (053 audit acceptance and 054 requirements); the serving DB records 054. Do not automatically upgrade/downgrade/restore while cleaning Git branches; schema lineage/bootstrap needs its own reviewed procedure.

## 4. Tests

Main source integration was manually validated with 149 backend auth/revision tests in a clean dependency environment and the candidate app image, 312 full frontend tests, lint, Next production build/TypeScript, backend Docker build, and read-only live host/image/schema preflight. The 203-file source/template manifest records the verified backend inputs. This is not complete customer-pilot acceptance. New changes require their own relevant checks and evidence.

## 5. Improvements

Keep one clean main checkout and separate worktrees for simultaneous topics. Record the active worktree, branch, commit, remaining WIP and exact resume point at session handoff. Consider CI/CD only when the owner resumes that scope; do not request workflow-token scope for routine source-only work.
