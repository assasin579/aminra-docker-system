from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/041_module_registry.py"
_SPEC = importlib.util.spec_from_file_location("module_registry_migration", _MIGRATION_PATH)
assert _SPEC and _SPEC.loader
MIGRATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MIGRATION)

EXPECTED_MODULES = {
    "certification_dossier",
    "document_management",
    "supplier_management",
    "traceability",
    "process_digitization",
    "workforce",
    "daily_operations",
    "audit_compliance",
    "public_trace",
    "notifications",
}


async def _reset_module_tables(db):
    for sql in MIGRATION.DOWN_SQL:
        await db.execute(sql)


@pytest.fixture
async def migrated(db_tx):
    await _reset_module_tables(db_tx)
    for sql in MIGRATION.UP_SQL:
        await db_tx.execute(sql)
    try:
        yield db_tx
    finally:
        await _reset_module_tables(db_tx)


async def test_module_registry_tables_and_seed_modules_exist(migrated):
    tables = {
        r["tablename"]
        for r in await migrated.fetch(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname='public' AND tablename = ANY($1::text[])
            """,
            ["modules", "business_model_modules", "tenant_modules", "module_dependencies"],
        )
    }
    assert tables == {"modules", "business_model_modules", "tenant_modules", "module_dependencies"}

    rows = await migrated.fetch("SELECT code, enabled FROM modules ORDER BY display_order, code")
    codes = {r["code"] for r in rows}
    assert EXPECTED_MODULES.issubset(codes)
    assert all(r["enabled"] for r in rows if r["code"] in EXPECTED_MODULES)


async def test_default_business_model_bundles_are_seeded(migrated):
    rows = await migrated.fetch(
        """
        SELECT i.code AS industry_code, m.code AS module_code, bmm.required, bmm.default_enabled
        FROM business_model_modules bmm
        JOIN industry_schemas i ON i.id = bmm.industry_schema_id
        JOIN modules m ON m.id = bmm.module_id
        WHERE i.code = ANY($1::text[])
        """,
        ["food_manufacturing", "restaurant_hotel", "livestock_slaughter"],
    )
    bundle = {(r["industry_code"], r["module_code"]): dict(r) for r in rows}

    assert bundle[("food_manufacturing", "traceability")]["required"] is True
    assert bundle[("food_manufacturing", "daily_operations")]["required"] is False
    assert bundle[("restaurant_hotel", "daily_operations")]["required"] is True
    assert bundle[("restaurant_hotel", "traceability")]["default_enabled"] is False
    assert bundle[("livestock_slaughter", "process_digitization")]["required"] is True
    assert bundle[("livestock_slaughter", "public_trace")]["default_enabled"] is False


async def test_module_dependencies_enforce_required_prerequisites(migrated):
    rows = await migrated.fetch(
        """
        SELECT m.code AS module_code, dep.code AS depends_on_code, md.dependency_type
        FROM module_dependencies md
        JOIN modules m ON m.id = md.module_id
        JOIN modules dep ON dep.id = md.depends_on_module_id
        """
    )
    deps = {(r["module_code"], r["depends_on_code"]): r["dependency_type"] for r in rows}

    assert deps[("public_trace", "traceability")] == "required"
    assert deps[("traceability", "supplier_management")] == "required"
    assert deps[("process_digitization", "traceability")] == "enhances"


async def test_existing_tenant_backfill_uses_selected_industry_defaults(db_tx, biz_a):
    await _reset_module_tables(db_tx)
    industry_id = await db_tx.fetchval(
        "SELECT id FROM industry_schemas WHERE code = 'food_manufacturing'"
    )
    if not industry_id:
        pytest.skip("industry_schemas seed data missing")

    await db_tx.execute(
        "UPDATE users SET industry_schema_id = $1 WHERE email = $2",
        industry_id,
        biz_a["email"],
    )

    for sql in MIGRATION.UP_SQL:
        await db_tx.execute(sql)

    rows = await db_tx.fetch(
        """
        SELECT m.code, tm.status, tm.source
        FROM tenant_modules tm
        JOIN modules m ON m.id = tm.module_id
        WHERE tm.tenant_id = $1
        """,
        biz_a["tenant_id"],
    )
    tenant_modules = {r["code"]: dict(r) for r in rows}

    assert tenant_modules["certification_dossier"]["status"] == "enabled"
    assert tenant_modules["traceability"]["status"] == "enabled"
    assert tenant_modules["daily_operations"]["status"] == "disabled"
    assert {r["source"] for r in rows} == {"migration"}

    await _reset_module_tables(db_tx)


async def test_downgrade_drops_module_registry_objects(migrated):
    for sql in MIGRATION.DOWN_SQL:
        await migrated.execute(sql)

    for table in ["tenant_modules", "business_model_modules", "module_dependencies", "modules"]:
        assert await migrated.fetchval("SELECT to_regclass($1)", f"public.{table}") is None

    # keep fixture finalizer idempotent
    for sql in MIGRATION.UP_SQL:
        await migrated.execute(sql)
