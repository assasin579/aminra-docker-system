# J1/J2 controlled completion

Source starts at main `2e1d476`. Selective candidate source: `ba369b0`.
The legacy dirty checkout and its unrelated changes remain preserved.
CI/CD remains deferred. Use a reviewed PR and manual rollout.

## Schema and data

Do not edit the applied 054 revision or run `upgrade heads` on the current
manually migrated installation. `scripts/operations/j1j2-schema.py` verifies
052/053 objects, rehearses additive 055 in a transaction, and reconciles the
verified lineage to merge revision 056. Default rolls back; `--apply` commits.
Use a migration credential, a verified backup and an exclusive maintenance
window. Lock timeout is 5 seconds and statement timeout is 60 seconds.

Existing direct document associations remain readable. They do not gain review
approval, new requirements bindings or attachment evidence automatically. An
owner may explicitly attach an existing version through the validated route.
Legacy unknown requirements stay unknown. Published requirement snapshots,
old revision packets and attached file identities remain immutable.

After durable attachment/submission evidence exists, 055 downgrade refuses.
Recover forward; retain the database and file volumes. Never restore an older
backup over live evidence as an application rollback. The old application image
is only a temporary recovery option with J1/J2 writes disabled.

Readiness selects the explicitly submitted dossier. A legacy NULL dossier may
be inferred only when the entire packet still identifies the same original
dossier and tenant. Reusing a file never imports another dossier's review round.
The owner's dossier-detail handoff link carries dossier_id into the submission
form; certification readiness is separate from sending evidence for CB review.

## Database boundary

Use `aminra_app` for backend and worker. It has no superuser, BYPASSRLS,
CREATE ROLE, CREATE DATABASE, replication or ownership privileges. Runtime DML
is granted explicitly; Alembic state is read-only and attachment associations
cannot be updated or deleted. Migration owner remains separate.

Vault app policy reads `secret/data/aminra/app-database`, not the administrative
`secret/data/aminra/database`. The rendered template contains only the runtime
DATABASE_URL. Validate both backend and worker after secret propagation/restart;
verify the runtime session role and denied DDL/role-changing operations.
This is an application-enforced shared-schema tenant model; it does not claim
RLS coverage.

## Acceptance

Use the retained 18-ID J1/J2 acceptance matrix as the explicit denominator.
Retain historical synthetic results separately. Each new result must identify
commit, image IDs, schema revision, actors, run ID and evidence files.
Real Keycloak tokens, rendered UI and HTTP/storage bytes must be exercised.
No final PASS based solely on mocked route calls or old-image evidence.
