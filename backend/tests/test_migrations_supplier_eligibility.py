from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest


_MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/038_cb_supplier_certificate_eligibility.py"
_SPEC = importlib.util.spec_from_file_location("p0a_supplier_eligibility_migration", _MIGRATION_PATH)
assert _SPEC and _SPEC.loader
MIGRATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MIGRATION)


@pytest.fixture
async def migrated(db_tx):
    await db_tx.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    await db_tx.execute("DROP TABLE IF EXISTS certificate_risk_alerts CASCADE")
    await db_tx.execute("DROP TABLE IF EXISTS supply_relationships CASCADE")
    await db_tx.execute("DROP TABLE IF EXISTS supplier_eligibilities CASCADE")
    await db_tx.execute("DROP TYPE IF EXISTS supplier_certificate_status CASCADE")
    for sql in MIGRATION.UP_SQL:
        await db_tx.execute(sql)
    try:
        yield db_tx
    finally:
        for sql in MIGRATION.DOWN_SQL:
            await db_tx.execute(sql)


async def test_schema_objects_indexes_exist(migrated):
    tables = set(
        await migrated.fetch(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname='public' AND tablename = ANY($1::text[])
            """,
            ["supplier_eligibilities", "supply_relationships", "certificate_risk_alerts"],
        )
    )
    assert {r["tablename"] for r in tables} == {
        "supplier_eligibilities",
        "supply_relationships",
        "certificate_risk_alerts",
    }

    enum_values = await migrated.fetch(
        """
        SELECT enumlabel FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        WHERE t.typname='supplier_certificate_status'
        ORDER BY enumsortorder
        """
    )
    assert [r["enumlabel"] for r in enum_values] == [
        "active",
        "expired",
        "suspended",
        "revoked",
        "pending_review",
    ]

    indexes = {r["indexname"] for r in await migrated.fetch("SELECT indexname FROM pg_indexes WHERE schemaname='public'")}
    assert "idx_supplier_eligibilities_tenant_supplier_status_dates" in indexes
    assert "idx_supply_relationships_buyer_active" in indexes
    assert "idx_certificate_risk_alerts_impacted_status" in indexes


async def test_enum_rejects_unknown_status(migrated, biz_a):
    sid = (await migrated.fetchrow(
        "INSERT INTO suppliers (tenant_id, name) VALUES ($1,'Enum Reject') RETURNING id",
        biz_a["tenant_id"],
    ))["id"]

    nested = migrated.transaction()
    await nested.start()
    with pytest.raises(Exception):
        await migrated.execute(
            """
            INSERT INTO supplier_eligibilities
              (supplier_id, tenant_id, certificate_no, issuer_name, status, valid_from, valid_until)
            VALUES ($1,$2,'CERT','CB','unknown',CURRENT_DATE,CURRENT_DATE + 10)
            """,
            sid,
            biz_a["tenant_id"],
        )
    await nested.rollback()


async def test_missing_supplier_fk_rejected_and_valid_rows_accepted(migrated, biz_a):
    nested = migrated.transaction()
    await nested.start()
    with pytest.raises(Exception):
        await migrated.execute(
            """
            INSERT INTO supplier_eligibilities
              (supplier_id, tenant_id, certificate_no, issuer_name, status, valid_from, valid_until)
            VALUES ($1,$2,'CERT-MISSING','CB','active',CURRENT_DATE,CURRENT_DATE + 10)
            """,
            str(uuid4()),
            biz_a["tenant_id"],
        )
    await nested.rollback()

    sid = (await migrated.fetchrow(
        "INSERT INTO suppliers (tenant_id, name) VALUES ($1,'Valid FK') RETURNING id",
        biz_a["tenant_id"],
    ))["id"]
    cert = await migrated.fetchrow(
        """
        INSERT INTO supplier_eligibilities
          (supplier_id, tenant_id, certificate_no, issuer_name, status, valid_from, valid_until)
        VALUES ($1,$2,'CERT-OK','CB','active',CURRENT_DATE,CURRENT_DATE + 10)
        RETURNING id, source_of_truth, scope
        """,
        sid,
        biz_a["tenant_id"],
    )
    rel = await migrated.fetchrow(
        """
        INSERT INTO supply_relationships (buyer_tenant_id, supplier_tenant_id, supplier_id, status)
        VALUES ($1,$2,$3,'active') RETURNING id
        """,
        biz_a["tenant_id"],
        biz_a["tenant_id"],
        sid,
    )
    alert = await migrated.fetchrow(
        """
        INSERT INTO certificate_risk_alerts
          (impacted_tenant_id, supplier_id, certificate_id, event_type, severity, message)
        VALUES ($1,$2,$3,'revoked','critical','revoked') RETURNING id
        """,
        biz_a["tenant_id"],
        sid,
        cert["id"],
    )

    assert cert["source_of_truth"] == "cb"
    assert json.loads(cert["scope"]) == {}
    assert rel["id"]
    assert alert["id"]


async def test_downgrade_drops_objects(migrated):
    for sql in MIGRATION.DOWN_SQL:
        await migrated.execute(sql)

    exists = await migrated.fetchval("SELECT to_regclass('public.supplier_eligibilities')")
    enum_exists = await migrated.fetchval("SELECT to_regtype('public.supplier_certificate_status')")

    assert exists is None
    assert enum_exists is None
    # keep fixture finalizer idempotent
    for sql in MIGRATION.UP_SQL:
        await migrated.execute(sql)
