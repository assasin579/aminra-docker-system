from __future__ import annotations

from datetime import date, timedelta
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest

from supply_chain.eligibility_service import (
    evaluate_supplier_eligibility,
    find_impacted_buyers,
    is_supplier_eligible,
    list_eligible_suppliers,
)
from supply_chain.models import SupplierCreate
from supply_chain.supplier_router import create_supplier

_MIGRATION_PATHS = [
    Path(__file__).resolve().parents[1] / "alembic/versions/038_cb_supplier_certificate_eligibility.py",
    Path(__file__).resolve().parents[1] / "alembic/versions/039_supplier_authority_batch_snapshot.py",
]
MIGRATIONS = []
for idx, migration_path in enumerate(_MIGRATION_PATHS):
    spec = importlib.util.spec_from_file_location(f"supplier_eligibility_migration_{idx}", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    MIGRATIONS.append(migration)


@pytest.fixture(autouse=True)
async def _p0a_schema(db_tx):
    """Run P0-A schema in-test so service tests stay isolated and fail-closed.

    The dev database may not yet be migrated while TDD is in progress. DDL is
    inside the outer db_tx transaction, so these drops/creates roll back after
    each test and do not mutate persistent dev data.
    """
    await db_tx.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    for migration in reversed(MIGRATIONS):
        for sql in migration.DOWN_SQL:
            await db_tx.execute(sql)
    for migration in MIGRATIONS:
        for sql in migration.UP_SQL:
            await db_tx.execute(sql)


async def _supplier(db, user, name="Elig Supplier"):
    r = await create_supplier(SupplierCreate(name=f"{name} {uuid4().hex[:6]}"), user=user, db=db)
    return r["id"]


async def _elig(db, sid, tenant_id, *, status="active", source="cb", scope=None, vf=None, vu=None):
    today = date.today()
    row = await db.fetchrow(
        """
        INSERT INTO supplier_eligibilities
          (supplier_id, tenant_id, certificate_no, issuer_name, status,
           valid_from, valid_until, scope, source_of_truth)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)
        RETURNING id
        """,
        sid,
        tenant_id,
        f"CB-{uuid4().hex[:8]}",
        "Test CB",
        status,
        vf or (today - timedelta(days=1)),
        vu or (today + timedelta(days=30)),
        scope if scope is not None else '{}',
        source,
    )
    return row["id"]


async def test_active_valid_cb_certificate_is_eligible(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)
    await _elig(db_tx, sid, biz_a["tenant_id"], scope='{"material_categories":["meat"]}')

    result = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], sid, "meat")

    assert result.eligible is True
    assert result.reason == "eligible"
    assert await is_supplier_eligible(db_tx, biz_a["tenant_id"], sid, "meat") is True


@pytest.mark.parametrize("status", ["expired", "suspended", "revoked", "pending_review"])
async def test_non_active_statuses_are_ineligible(db_tx, biz_a, status):
    sid = await _supplier(db_tx, biz_a)
    await _elig(db_tx, sid, biz_a["tenant_id"], status=status)

    result = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], sid)

    assert result.eligible is False
    assert status in result.reason


async def test_expired_by_date_is_ineligible_even_when_status_active(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)
    await _elig(db_tx, sid, biz_a["tenant_id"], vu=date.today() - timedelta(days=1))

    result = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], sid)

    assert result.eligible is False
    assert result.reason == "certificate_expired"


async def test_future_valid_from_is_ineligible(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)
    await _elig(db_tx, sid, biz_a["tenant_id"], vf=date.today() + timedelta(days=1))

    result = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], sid)

    assert result.eligible is False
    assert result.reason == "certificate_not_yet_valid"


async def test_wrong_tenant_and_missing_row_fail_closed(db_tx, biz_a, biz_b):
    sid = await _supplier(db_tx, biz_a)
    await _elig(db_tx, sid, biz_a["tenant_id"])

    wrong_tenant = await evaluate_supplier_eligibility(db_tx, biz_b["tenant_id"], sid)
    missing = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], str(uuid4()))

    assert wrong_tenant.eligible is False
    assert wrong_tenant.reason == "supplier_not_found"
    assert missing.eligible is False
    assert missing.reason == "supplier_not_found"


async def test_source_of_truth_must_be_cb(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)
    await _elig(db_tx, sid, biz_a["tenant_id"], source="supplier_upload")

    result = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], sid)

    assert result.eligible is False
    assert result.reason == "source_of_truth_not_cb"


async def test_scope_policy_material_specific_fails_closed_empty_scope_but_no_material_ok(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)
    await _elig(db_tx, sid, biz_a["tenant_id"], scope='{}')

    material_specific = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], sid, "meat")
    no_material = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], sid)

    assert material_specific.eligible is False
    assert material_specific.reason == "scope_mismatch"
    assert no_material.eligible is True


async def test_scope_mismatch_is_ineligible(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)
    await _elig(db_tx, sid, biz_a["tenant_id"], scope='{"material_categories":["dairy"]}')

    result = await evaluate_supplier_eligibility(db_tx, biz_a["tenant_id"], sid, "meat")

    assert result.eligible is False
    assert result.reason == "scope_mismatch"


async def test_list_eligible_suppliers_filters_fail_closed(db_tx, biz_a):
    good = await _supplier(db_tx, biz_a, "Good")
    bad = await _supplier(db_tx, biz_a, "Bad")
    await _elig(db_tx, good, biz_a["tenant_id"], scope='{"material_categories":["meat"]}')
    await _elig(db_tx, bad, biz_a["tenant_id"], status="revoked", scope='{"material_categories":["meat"]}')

    rows = await list_eligible_suppliers(db_tx, biz_a["tenant_id"], "meat")

    assert [str(r["id"]) for r in rows] == [good]


async def test_active_relationship_impact_lookup(db_tx, biz_a, biz_b):
    sid = await _supplier(db_tx, biz_a)
    cert_id = await _elig(db_tx, sid, biz_a["tenant_id"])
    await db_tx.execute(
        """
        INSERT INTO supply_relationships
          (buyer_tenant_id, supplier_tenant_id, supplier_id, material_category, status)
        VALUES ($1,$2,$3,'meat','active'), ($4,$2,$3,'meat','paused')
        """,
        biz_b["tenant_id"],
        biz_a["tenant_id"],
        sid,
        str(uuid4()),
    )

    buyers = await find_impacted_buyers(db_tx, sid, cert_id)

    assert buyers == [biz_b["tenant_id"]]
