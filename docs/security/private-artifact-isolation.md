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


## Current identity-provider authority

Protected HTTP entry points, including admin helpers and query-token file routes,
verify token introspection, account enabled state and effective realm roles.
`KEYCLOAK_AUTHZ_TTL_SECONDS` defaults to30 and is capped at30; the cache is bounded
and keyed by issuer plus a token digest. Database changes apply per request.
Provider outages or missing reader credentials fail closed after fresh cached
verification expires; there is no fallback to stale JWT role claims.

Prefer a confidential `KEYCLOAK_AUTHZ_CLIENT_ID` / `KEYCLOAK_AUTHZ_CLIENT_SECRET`
service account with only realm-management `view-users`. It needs token
introspection and user/effective-role reads, and must fail user mutations.
Existing deployments can use the already configured admin service credential as
an operational fallback; this does not add a permission grant. Dedicated-reader
provisioning and credential handling remain an explicit operations check.

Legacy service-worker queue entries embed bearer credentials without scoped
ownership. Their background replay is removed and session changes request deletion
of the legacy private IndexedDB database. Blocked deletion is reported as blocked,
not falsely declared successful. A new offline workflow must obtain fresh,
actor-and-tenant scoped authorization and must not silently reuse the old queue.


Verified profiles refresh when the tab becomes visible, on `pageshow`, and every
10 seconds while visible. Backend authority verification has a shared 7-second
budget; each identity-provider request retains its 3-second timeout. The browser
allows 9 seconds, below the polling interval, so a valid multi-step check taking
more than 5 seconds can complete without an unbounded authorization window.
Verification never authorizes an old identity after a newer session wins.

Failures log only a random trace, fixed step name, exception class, upstream
status and elapsed time. Login responses forward validated diagnostic headers,
never upstream error text. Current DB lookup uses the Keycloak subject first and
rejects conflicting subject/email mappings; a changed email cannot bypass a
suspension or restore stale owner claims.

Audit transactions use function-scoped dependencies so commit completes before
success headers are sent. This preserves parent/assignment locks through the
handler while preventing a successful receipt for a failed commit. ASGI-send
ordering tests cover success and commit failure; buffered clients alone cannot
establish that ordering. Login controls remain disabled in server-rendered HTML
until hydration attaches their handlers and restoration of a previous identity
finishes. The authorization-scope boundary may remount descendants when that
identity arrives; credential entry must wait until this initialization settles.
