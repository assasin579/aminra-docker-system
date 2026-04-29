# Feature #24 — Schema Design

**Stage 3** · linked to `spec.md` + `threat-model.md`. Migration `017_document_version_control`.

## A. Design principles

1. **Additive only** — every change is `ADD COLUMN nullable` or new constraint/index. **No DROP**, no RENAME, no NOT-NULL retrofitted on existing columns. Methodology section B compliance.
2. **Reversibility** — `def downgrade()` undoes every change (drop columns, drop triggers, drop indexes, restore default state). Test apply + rollback before merging.
3. **Backfill in same transaction** — migration UP runs in single TX; rollback on any constraint violation. Post-migration sanity query in runbook.
4. **Tenant integrity enforced at DB layer** — trigger validates `version_parent_id` and `superseded_by_id` point to same-tenant rows. Defends against application-layer bugs (R2 critical).
5. **Backwards compat for legacy `reviewed_by` / `reviewed_at`** — new `approver_id` / `approved_at` populated from these on backfill; both fields kept (don't drop legacy yet — that's destructive).

## B. Column additions

| Column | Type | Default | Nullable | Purpose |
|---|---|---|---|---|
| `version_number` | INT | 1 | NOT NULL | Version count within a chain |
| `version_parent_id` | UUID | NULL | YES | Previous version in chain. FK → documents(id) ON DELETE SET NULL |
| `approver_id` | UUID | NULL | YES | User who approved. FK → users(id) ON DELETE SET NULL |
| `approved_at` | TIMESTAMPTZ | NULL | YES | When approval occurred |
| `effective_date` | DATE | NULL | YES | Operational start date (may differ from approved_at) |
| `next_review_date` | DATE | NULL | YES | Periodic review deadline (JAKIM §5.5.2) |
| `retention_period_days` | INT | 1825 | NOT NULL | Min 5 years (CHECK ≥ 1825). Audit-grade requirement. |
| `retention_expires_at` | TIMESTAMPTZ | NULL | YES | Auto-computed by trigger on approve. Stored for query-speed (not just derived) |
| `superseded_by_id` | UUID | NULL | YES | Next version that obsoletes this. FK → documents(id) ON DELETE SET NULL |
| `approval_status` | VARCHAR(20) | 'draft' | NOT NULL | State machine: draft / pending_approval / approved / obsolete (CHECK constraint) |

## C. Constraints

```sql
-- Approval status enum constraint
CHECK (approval_status IN ('draft', 'pending_approval', 'approved', 'obsolete'))

-- Retention floor (R4 mitigation, audit-grade)
CHECK (retention_period_days >= 1825)
```

## D. Tenant integrity trigger (R2 mitigation)

Postgres CHECK constraints can't reference other rows. Use BEFORE INSERT/UPDATE trigger:

```sql
CREATE OR REPLACE FUNCTION enforce_documents_chain_tenant()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  -- 1. version_parent_id must point to same tenant
  IF NEW.version_parent_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM documents
      WHERE id = NEW.version_parent_id AND tenant_id = NEW.tenant_id
    ) THEN
      RAISE EXCEPTION
        'version_parent_id (%) must reference document in same tenant (%)',
        NEW.version_parent_id, NEW.tenant_id
        USING ERRCODE = '23514';
    END IF;
  END IF;

  -- 2. superseded_by_id must point to same tenant
  IF NEW.superseded_by_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM documents
      WHERE id = NEW.superseded_by_id AND tenant_id = NEW.tenant_id
    ) THEN
      RAISE EXCEPTION
        'superseded_by_id (%) must reference document in same tenant (%)',
        NEW.superseded_by_id, NEW.tenant_id
        USING ERRCODE = '23514';
    END IF;
  END IF;

  -- 3. Auto-compute retention_expires_at on approval
  IF NEW.approval_status = 'approved' AND NEW.approved_at IS NOT NULL
     AND (TG_OP = 'INSERT' OR OLD.approval_status IS DISTINCT FROM 'approved') THEN
    NEW.retention_expires_at := COALESCE(NEW.effective_date::TIMESTAMPTZ, NEW.approved_at)
                              + (NEW.retention_period_days || ' days')::INTERVAL;
  END IF;

  -- 4. Auto-set obsolete when superseded_by_id is set
  IF NEW.superseded_by_id IS NOT NULL
     AND (TG_OP = 'INSERT' OR OLD.superseded_by_id IS NULL) THEN
    NEW.approval_status := 'obsolete';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER documents_chain_tenant_check
  BEFORE INSERT OR UPDATE ON documents
  FOR EACH ROW EXECUTE FUNCTION enforce_documents_chain_tenant();
```

## E. Delete-block trigger (per Stage 2 sign-off Q1)

Deleting a doc that other docs point to via `version_parent_id` would break chain integrity. Block:

```sql
CREATE OR REPLACE FUNCTION block_delete_with_children()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM documents WHERE version_parent_id = OLD.id) THEN
    RAISE EXCEPTION
      'Cannot delete document % — it has %s child version(s). Supersede chain first.',
      OLD.id, (SELECT COUNT(*) FROM documents WHERE version_parent_id = OLD.id)
      USING ERRCODE = '23503', HINT = 'Use POST /api/documents/{id}/supersede or delete children first';
  END IF;
  RETURN OLD;
END;
$$;

CREATE TRIGGER documents_block_delete_with_children
  BEFORE DELETE ON documents
  FOR EACH ROW EXECUTE FUNCTION block_delete_with_children();
```

NOTE: this changes existing DELETE behaviour. Callers that delete a doc that happens to have child versions will now get 500 unless they handle the exception. Mitigation: application layer catches 23503 SQLSTATE and returns 409 with message; tested in INT-43..44.

## F. Indexes

```sql
-- Filter docs by approval state per tenant (dashboard, list pages)
CREATE INDEX idx_documents_tenant_approval
  ON documents(tenant_id, approval_status);

-- Upcoming review reports
CREATE INDEX idx_documents_tenant_next_review
  ON documents(tenant_id, next_review_date)
  WHERE next_review_date IS NOT NULL;

-- Chain traversal (children of a parent)
CREATE INDEX idx_documents_version_parent
  ON documents(version_parent_id)
  WHERE version_parent_id IS NOT NULL;

-- Reverse chain (find original)
CREATE INDEX idx_documents_superseded_by
  ON documents(superseded_by_id)
  WHERE superseded_by_id IS NOT NULL;

-- Retention expiry reports
CREATE INDEX idx_documents_tenant_retention
  ON documents(tenant_id, retention_expires_at)
  WHERE retention_expires_at IS NOT NULL;
```

5 partial indexes (use `WHERE … IS NOT NULL`) keep index size bounded since most pre-existing docs have NULLs after migration backfill.

## G. Backfill rules (in single TX with migration)

```sql
-- Rule 1: existing 'approved' rows → approval_status='approved' + carry over reviewer
UPDATE documents
   SET approval_status = 'approved',
       approver_id = reviewed_by,            -- may be NULL for very old rows; allowed
       approved_at = reviewed_at,
       version_number = 1
 WHERE status = 'approved';

-- Rule 2: existing 'uploaded' / 'reviewing' rows → draft
UPDATE documents
   SET approval_status = 'draft',
       version_number = 1
 WHERE status IN ('uploaded', 'reviewing');

-- Rule 3: existing 'rejected' rows → draft (per spec §4 mapping)
UPDATE documents
   SET approval_status = 'draft',
       version_number = 1
 WHERE status = 'rejected';
```

After backfill, every row has: `approval_status` set (NOT NULL constraint satisfied), `version_number=1`, `retention_period_days=1825`, `retention_expires_at` NULL (only computed on future approval transitions). For pre-existing approved rows, `retention_expires_at` STAYS null until something triggers an UPDATE — acceptable since these are legacy rows where retention started from `reviewed_at` and we don't have a reliable effective_date.

**Optional follow-up backfill** (not in this migration; do as data-fix script): for legacy approved rows with `reviewed_at IS NOT NULL`, populate `retention_expires_at = reviewed_at + INTERVAL '1825 days'`. Defer because risky to run in same migration TX with potentially huge dataset.

## H. Verification queries (post-migration)

Run these in runbook (Stage 8):

```sql
-- 1. Schema added
SELECT column_name, data_type, is_nullable, column_default
  FROM information_schema.columns
 WHERE table_name = 'documents'
   AND column_name IN ('version_number','version_parent_id','approver_id',
                       'approved_at','effective_date','next_review_date',
                       'retention_period_days','retention_expires_at',
                       'superseded_by_id','approval_status')
 ORDER BY column_name;
-- Expect: 10 rows.

-- 2. Trigger active
SELECT tgname, tgenabled
  FROM pg_trigger
 WHERE tgrelid = 'documents'::regclass
   AND tgname IN ('documents_chain_tenant_check', 'documents_block_delete_with_children');
-- Expect: 2 rows, tgenabled='O' (origin = active).

-- 3. Backfill cross-tab — every row should have approval_status set
SELECT status AS legacy_status, approval_status, COUNT(*)
  FROM documents
 GROUP BY status, approval_status
 ORDER BY status, approval_status;
-- Expect:
--   approved | approved | N
--   uploaded | draft    | N
--   reviewing | draft   | N
--   rejected | draft    | N
-- No NULL in approval_status column.

-- 4. NOT NULL invariants hold
SELECT COUNT(*) FROM documents WHERE approval_status IS NULL OR version_number IS NULL OR retention_period_days IS NULL;
-- Expect: 0.

-- 5. Retention floor honored
SELECT MIN(retention_period_days), MAX(retention_period_days) FROM documents;
-- Expect: min=1825 (or higher).

-- 6. Tenant integrity trigger functional — manually test:
-- Try INSERT INTO documents(tenant_id=A, version_parent_id=<doc in tenant B>)
-- Expect: error 23514, message references "same tenant".
```

## I. Rollback

```sql
-- downgrade()
DROP TRIGGER IF EXISTS documents_block_delete_with_children ON documents;
DROP TRIGGER IF EXISTS documents_chain_tenant_check ON documents;
DROP FUNCTION IF EXISTS block_delete_with_children();
DROP FUNCTION IF EXISTS enforce_documents_chain_tenant();

DROP INDEX IF EXISTS idx_documents_tenant_retention;
DROP INDEX IF EXISTS idx_documents_superseded_by;
DROP INDEX IF EXISTS idx_documents_version_parent;
DROP INDEX IF EXISTS idx_documents_tenant_next_review;
DROP INDEX IF EXISTS idx_documents_tenant_approval;

ALTER TABLE documents
  DROP COLUMN IF EXISTS approval_status,
  DROP COLUMN IF EXISTS superseded_by_id,
  DROP COLUMN IF EXISTS retention_expires_at,
  DROP COLUMN IF EXISTS retention_period_days,
  DROP COLUMN IF EXISTS next_review_date,
  DROP COLUMN IF EXISTS effective_date,
  DROP COLUMN IF EXISTS approved_at,
  DROP COLUMN IF EXISTS approver_id,
  DROP COLUMN IF EXISTS version_parent_id,
  DROP COLUMN IF EXISTS version_number;
```

WARNING: downgrade is destructive (deletes approval data). Only run if feature must be fully reverted; backup first.

## J. Permission flag (NOT a schema change — code-only)

`can_approve_documents` is a NEW permission name. Implementation in `auth/permissions.py`:

```python
def get_user_permissions(user_row: dict) -> dict:
    return {
        ...,  # existing
        "can_approve_documents": (
            user_row.get("is_owner", False)
            or "ihc_role" in user_row and user_row["ihc_role"] is not None
            or _explicit_permissions(user_row).get("can_approve_documents", False)
        ),
    }
```

No `users` table change needed; permission is computed from existing fields + optional explicit override in `users.permissions` JSONB (existing).

## K. Test data hygiene plan (per methodology section I)

After Stage 6 test run completes:
- Truncate `documents` rows where `tenant_id = <test seed tenant_id>`
- Drop test backups under `/data/test_*` if any
- Document disk-usage delta in Stage 8 runbook

## L. Sign-off

Stage 3 complete when:
- [x] All column additions documented with type + default + nullable
- [x] Constraints (CHECK) explicit
- [x] Trigger functions reviewed (tenant integrity + delete block + retention auto-compute)
- [x] Index strategy with rationale (5 partial indexes)
- [x] Backfill rules cover all 4 legacy `status` values
- [x] Verification queries listed for runbook
- [x] Rollback path tested-able
- [x] Permission addition documented (code-only, no schema change)

Migration file landing in `backend/alembic/versions/017_document_version_control.py` next.

→ Stage 4 (Test plan upfront, ≥300 cases listed) once user signs off this design.
