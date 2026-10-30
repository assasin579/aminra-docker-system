# AMINRA source workflow

`main` is the canonical reviewed source. Work through focused `feat/*`, `fix/*` or `docs/*` branches and PRs with manual validation evidence.

- [Git workflow and branch roles](docs/operations/git-workflow.md)
- [ADR-009: main authority; CI/CD deferred](docs/architecture/adr/ADR-009-main-release-authority.md)
- [Verified operational backend source inputs](docs/operations/verified-runtime-source-manifest.json)

CI/CD is deferred. Legacy GitHub workflows are disabled; merging source does not deploy or change the database. Runtime is tracked separately by source commit and exact FE/BE image IDs. Root compose is legacy local development, not an approved production cutover procedure.
