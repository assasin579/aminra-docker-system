# Automated UAT operations

## Purpose and acceptance boundary

The owner authorized automating execution, evidence and retests on 2026-10-31.
This suite runs the application through real browsers and supplements it with
explicitly labelled API security checks. It does not grant pilot approval.

The canonical baseline remains the vault's `testing/uat-master-checklist.md`
and `uat-execution-register.csv`: 160 controls, 14 E2E journeys, 8 scope decisions.
`baseline-catalog.json` is a generated snapshot with candidate case references,
not a second source of business policy. The CSV may include historical case
rows; inventory/reporting exclude these from the baseline denominator.

Current implementation is **partial baseline coverage**. It provides a working
isolated runner and executable dossier/submission/revision/authentication cases.
Controls without a complete reviewed acceptance decomposition remain Blocked;
a successful subcase never marks its entire parent control Pass. On 2026-10-31 the owner explicitly Excluded all eight commercial scope groups
from this UAT and retained them for a later phase; see `scope-decisions.json`.

## Run

Prerequisites: Docker, Python 3 standard library, Node, `npm ci` in
`frontend/aminra-web`, and Playwright browsers for the selected project. Install
only the project's locked dependencies. No credentials or customer data are
needed. Images must already exist locally.

From the repository root:

```bash
python3 scripts/uat/run.py
```

The runner holds a per-user exclusive lock for setup, browser execution, recovery
and cleanup. An overlapping invocation exits1before Docker setup. Run desktop,
mobile and other browser projects sequentially; Docker network creation/removal
can interrupt another Chromium run with `ERR_NETWORK_CHANGED`. Do not replace a
failed navigation with an automatic retry or call that run a clean pass.

The default full suite includes core and extended workflow checks. Use
`--suite core` for the established dossier/authentication regression subset;
that selection does not change the full-baseline acceptance gate.

The default images are the verified 5457cf8 release. For a new release, explicitly
supply the intended immutable backend/frontend image references:

```bash
python3 scripts/uat/run.py \
  --backend-image aminra-backend:document-domain-5457cf8 \
  --frontend-image aminra-frontend:document-domain-5457cf8 \
  --project desktop
```

The default schema source is the serving AMINRA PostgreSQL container. The only
source operations are `SELECT version_num` and `pg_dump --schema-only --no-owner
--no-acl`. They do not copy customer rows or migrate/change production. An offline
schema file can be provided with `--schema-file` and `--schema-head`; the caller
is responsible for providing a schema-only file. This is a schema-clone test,
not proof that the entire historical migration chain upgrades a fresh database.

Outputs live in a private ignored `.uat-runs/<run-id>/` directory, or in a path
selected with `--output`. HTML/JSON/CSV reports include build/image/schema,
subcases, parent references, failures and all baseline gaps. Playwright failure
artifacts include traces, screenshots and videos; explicit successful journey
screenshots/evidence are attached. Inline JSON-reporter attachments are also
materialized under private `inline-evidence/` files and linked from the HTML
summary. Browser/API results remain distinguishable.

Exit codes:

- `0`: selected technical acceptance passed. `--suite j1j2` uses its explicit18criteria gate; this does not pass the complete baseline.
- `1`: a test, setup, recovery or cleanup failed.
- `2`: executable tests passed; the full baseline is still incomplete/Blocked.

A pass on retry is flaky, not a clean pass. Required missing credentials/data
are failures or Blocked. There are no skips or retries in this suite.

## Environment and credentials

Each run creates a random labelled Docker network plus dedicated PostgreSQL,
Keycloak realm, backend and frontend containers. Only random loopback ports are
published. The network is separate from production; it is not an outbound
firewall. LLM keys are empty, no live mail/payment/blockchain configuration is
injected, and browser navigation is restricted to the run origin.

Eight generated identities cover two businesses, two CBs, an admin, a read-only
member, an assigned auditor and an unassigned auditor. Passwords/configuration
exist only in a mode-0600 temporary directory, removed on normal completion or
SIGTERM. The application connects as non-superuser `aminra_app`; the test role
cannot mutate migration state or immutable attachment rows. Domain actions under
acceptance run through the UI; API fixture setup and API-only assertions are
labelled separately. The schema is empty before identities are seeded.

Artifacts are private: traces may contain synthetic credentials, bearer tokens
and QA identifiers. Do not commit or publicly upload them. After environment
teardown, these identities and tokens have no remaining running realm. Retain
only the evidence needed for audit and remove it according to the agreed policy.

## Recovery and cleanup

After a clean core run, the runner dumps only its synthetic database, stops its
own backend, recreates/restores its own database, starts the same backend and
performs another real browser login/dossier/file-hash check. Keycloak and file
storage remain intact. This is **database recovery**, not a full disaster-recovery
or certificate-public-verification acceptance. Operation duration is recorded;
no unapproved RPO/RTO threshold is invented. A random published port can change
on restart, so readiness discovers the current mapping again.

Finally, owned containers and anonymous volumes are removed, then the network.
Names and exact run labels are checked before removal. Existing non-UAT runtime
IDs/images/start times are compared before/after. A cleanup problem prevents a
successful execution gate.

SIGKILL or host failure cannot run Python cleanup. Recover with the exact run
manifest (the command refuses production names or mismatched labels):

```bash
python3 scripts/uat/cleanup.py .uat-runs/<run-id>/resources.json
```

This does not reset or delete production data. It also does not grant permission
to delete historical evidence or customer audit records.

## Maintain and extend

```bash
python3 -m unittest discover -s scripts/uat -p 'test_*.py' -v
python3 scripts/uat/inventory.py \
  /home/user/Documents/all-docs/02-Projects/aminra/testing/uat-execution-register.csv \
  --output docs/testing/uat/baseline-catalog.json
```

Add deterministic, independent scenarios with stable case names and `@CONTROL-ID`
references. Use `[API]` for API-only checks. A case cannot claim full parent
acceptance just because it contains a few matching references. Keep immutable
requirements versions, denied roles, wrong tenants, lost responses and genuine
user-visible outcomes in assertions. No database seeding of the state transition
being tested; no mocks of successful business outcomes.

Remaining work includes full acceptance decomposition for every control, other
end-to-end journeys, role reassignment/revocation, broader certificate lifecycle,
onsite/offline devices, real external integrations and independent business
oracles. Existing legacy specs are candidates for migration, not inherited Pass.

Cross-browser configurations exist, but running a configured browser is distinct
from completing all device acceptance. Do not describe desktop-forced journey
contexts as physical iPhone/Safari or mobile-offline validation.

No GitHub workflow, scheduler, automatic deployment or automatic merge is enabled.
CI/CD remains deferred. The runner is invoked explicitly by the operator/agent.

## Verified checkpoint

See [FINDINGS.md](FINDINGS.md): complaint/conflict source fixes are verified in
an expanded21-subcase desktop run,8mobile-emulation trust cases,371frontend
checks and25runner checks. The
complete baseline is still BLOCKED with partial coverage;8owner-excluded groups
remain N/A. Source is uncommitted and serving main5457cf8 is unchanged.

The default images still target that serving release and reproduce its known
static-form failures. To verify the local repaired candidate, explicitly select
its already-built immutable frontend image:

```bash
python3 scripts/uat/run.py --frontend-image sha256:2ab20680b1895865686dce074a44919513506c4ea711e16fc89a2eb0729ae45e
```

This is candidate verification, not a deployment or committed-main release.

## J1/J2 coverage pack

Use `python3 scripts/uat/run.py --suite j1j2` for the dedicated acceptance pack.
See [J1-J2.md](J1-J2.md) and [j1j2-manifest.json](j1j2-manifest.json) for required
branch coverage and evidence. It has its own technical gate, independent from
the broader baseline and its known complaint/conflict UI defects.
