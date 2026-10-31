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

## J1/J2 UX closeout

This patch publishes the frontend UX changes initially deployed from an
uncommitted snapshot based on main593c3a9. It preserves the owner/delegated
upload boundaries, explicit login issuer and cancelled-dossier readability.

- Revision-required, rejected and unknown states have explicit labels. CB
  corrections use the feedback form; the competing returned-status button is
  removed. Existing returned packets retain contextual guidance.
- List, packet, history and submit-setup failures have error/retry states.
  Late responses cannot populate another actor's or packet's view. Correction
  controls wait for a successfully loaded packet/history.
- Submission shows the dossier, standard and pinned requirement version.
  Mutation failures remain in the dialog; unchanged retries retain their key.
- Historical feedback resolves filenames from each round's snapshot. A
  resolved revision is described as business resubmission, not CB acceptance.
- Template creation retains the source dossier's pinned requirement types and
  links back to its attachment slots. Downloaded drafts still require explicit
  attachment. Template contents are not immutable certification approvals.
- Named dialogs trap focus and restore the trigger; forms have accessible
  names. Token refresh preserves drafts; account changes clear scoped data.

### Validation and deployment provenance

Final source verification:360/360FEtests across57files, scoped ESLint with zero
warnings, Docker npm-ci/Next16.4.2webpack production build including TypeScript,
and2source-only Playwright visibility contracts PASS. The static contracts do
not launch a browser.

The initial serving image3ebbeb5009f8 was built from289frontend input files,
manifestfe66808cf41fa4327afb4fb51ca82097621f18c679bc59bc14f9deeeac14216c.
Post-deploy checks passed12local/publicroutes and20image/local/publicasset hashes,
invalidlogin/API401 and issuer metadata200. Runtime env/network/mount/ports and
21othercontainers were preserved. No backend/schema/CI/CD changes belong to this
patch. Evidence: `/home/user/Downloads/aminra-j1j2-ux-20261030/deploy/`.

After the reviewed merge, verify all289Git blobs against that manifest before
promoting source metadata. A metadata-only image promotion must retain identical
filesystem layers and runtime configuration; record the resulting main commit,
image identity and post-recreation checks. Do not label an unverified rebuild as
the accepted image.

The first deployment rolled back safely when Cloudflare1010 blocked the default
Python-urllib client. The same denial reproduced on the old baseline. The
explicit `AMINRA-Deployment-Check/1.0` client passed identical baseline and final
checks; no Cloudflare policy change was made. Keep baseline-client comparison
and rollback ready for future manual releases.

Real Business/CB two-round, mobile and keyboard browser acceptance remains a
separate gate, as does independent QA/CB sign-off and customer-pilot approval.
