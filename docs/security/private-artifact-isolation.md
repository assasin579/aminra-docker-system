# Private artifact isolation

Authenticated API credentials identify a candidate principal; current application
user status, organization and owner authority come from the database on every
request. Existing Keycloak subject bindings cannot be transferred by matching an
email. New organization owners receive their own application tenant; staff must
have the projection created by the invitation transaction.

AI review files and public job handles are private to both their creator and
current tenant. Legacy review JSON and job handles without ownership metadata are
not automatically shared or migrated. Old files are retained, but new API reads
never fall back to their global filename paths.

## Shared reference knowledge

`POST /ingest` publishes shared reference material and requires a platform admin.
Regular uploads go through `/evaluate` or the document library and must not enter
the shared collection. Worker jobs default to non-public; publishing requires an
explicit trusted-producer flag. Search requires `public_reference=true` on every
keyword/vector branch. Untagged legacy chunks remain quarantined.

To import a separately reviewed, non-private reference from a controlled file:

```bash
python -m pipeline.ingest --file /path/to/reviewed-reference.pdf --public-reference
```

The operator must verify source, content and permission to share first. Do not
bulk-tag the old collection or ingest an entire customer upload directory as
public. No collection reset or historical-file deletion is required by this patch.
Until approved references are reimported, shared search can return fewer results.
That is an intentional fail-closed boundary, not proof that the corpus was audited.

## Browser persistence and exports

Private APIs, authenticated responses and private navigation/RSC responses are
network-only. Service worker v10 removes older caches and caches only allowlisted
static assets. Offline access to private APIs requires a separately authorized
actor-scoped design; a URL-only response cache is never a substitute.

Local evaluation state uses actor+tenant namespaces and is purged, along with
unattributable historical keys, on session changes. Logout and identity changes
invalidate pending responses and remount authorization-scoped descendants.
Exported evaluation HTML escapes all document/AI/reviewer text, has a restrictive
CSP and detaches its opener.

## Validation and operational limits

Run the principal, bootstrap, private-resource, shared-knowledge, audit and
document regression tests plus frontend session/cache/export tests. Real-token
revocation, real browser service-worker upgrade/offline tests and direct HTTP
cross-principal checks are separate acceptance requirements. A unit pass does
not establish full UAT or security completion.

Keep manual rollout and disposable UAT execution sequential: a live deployment
during a runner's protected-runtime snapshot invalidates its isolation proof.
Preserve configuration and exact image/source provenance, and retain rollback
containers. Prefer forward correction if rollback would reopen private-data paths.
