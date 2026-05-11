"""Phase 1 — Company rich-data + placeholder coverage tests (40 cases).

Covers:
  - services.template_field_coverage logic (unit, 18)
  - Migration 031 effect on schema (3 schema checks)
  - PATCH /auth/company-profile with new fields (8 integration)
  - GET /auth/company-profile returns new fields (3)
  - GET /api/templates/{doc_type}/placeholder-coverage (8)
"""
from __future__ import annotations

import os
import time
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from jose import jwt

from auth.jwt_utils import SECRET, ALGORITHM

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── Unit tests — template_field_coverage (18 tests) ────────────────────────


class TestCoverageUnit:
    def test_identity_fields_universal(self):
        from services.template_field_coverage import fields_for_doc_type, IDENTITY_FIELDS
        result = fields_for_doc_type("any_doc_type")
        for f in IDENTITY_FIELDS:
            assert f in result

    def test_unknown_doc_type_returns_identity_only(self):
        from services.template_field_coverage import fields_for_doc_type, IDENTITY_FIELDS
        result = fields_for_doc_type("fake_doc_type_xyz")
        assert result == tuple(IDENTITY_FIELDS)

    def test_halal_policy_includes_commitment_field(self):
        from services.template_field_coverage import fields_for_doc_type
        result = fields_for_doc_type("halal_policy")
        assert "halal_commitment_statement" in result

    def test_internal_halal_committee_includes_ihc_fields(self):
        from services.template_field_coverage import fields_for_doc_type
        result = fields_for_doc_type("internal_halal_committee")
        for f in ("ihc_chairman_name", "ihc_chairman_title", "ihc_inception_date",
                  "ihc_members_brief", "ihc_meeting_frequency"):
            assert f in result

    def test_ingredient_includes_supply_fields(self):
        from services.template_field_coverage import fields_for_doc_type
        result = fields_for_doc_type("ingredient_raw_material")
        for f in ("product_categories", "primary_suppliers",
                  "ingredient_origin_countries", "packaging_materials_brief"):
            assert f in result

    def test_has_manual_alias_halal_manual_same_fields(self):
        from services.template_field_coverage import fields_for_doc_type
        a = fields_for_doc_type("has_manual")
        b = fields_for_doc_type("halal_manual")
        assert set(a) == set(b)

    def test_dedup_when_identity_overlap(self):
        """Identity fields prepended; no duplicates if extra also lists identity field."""
        from services.template_field_coverage import fields_for_doc_type
        result = fields_for_doc_type("halal_policy")
        assert len(result) == len(set(result))

    def test_calculate_coverage_empty_user_zero_pct(self):
        from services.template_field_coverage import calculate_coverage
        r = calculate_coverage({}, "halal_policy")
        assert r["filled"] == 0
        assert r["coverage_pct"] == 0.0

    def test_calculate_coverage_partial_fill(self):
        from services.template_field_coverage import calculate_coverage
        r = calculate_coverage({"company_name": "X", "address": "Y"}, "halal_policy")
        assert r["filled"] == 2
        assert r["total_fields"] >= 8
        assert 0 < r["coverage_pct"] < 100

    def test_calculate_coverage_full_fill_100_pct(self):
        from services.template_field_coverage import calculate_coverage, fields_for_doc_type
        fields = fields_for_doc_type("internal_halal_committee")
        user_row = {f: f"value_{f}" for f in fields}
        r = calculate_coverage(user_row, "internal_halal_committee")
        assert r["filled"] == r["total_fields"]
        assert r["coverage_pct"] == 100.0

    def test_coverage_response_has_fields_array(self):
        from services.template_field_coverage import calculate_coverage
        r = calculate_coverage({}, "halal_policy")
        assert isinstance(r["fields"], list)
        for f in r["fields"]:
            assert "key" in f
            assert "label" in f
            assert "filled" in f

    def test_filled_value_preview_truncated(self):
        from services.template_field_coverage import calculate_coverage
        long_str = "A" * 100
        r = calculate_coverage({"company_name": long_str}, "company_profile")
        field = next(f for f in r["fields"] if f["key"] == "company_name")
        assert len(field["value_preview"]) <= 60

    def test_empty_string_not_filled(self):
        from services.template_field_coverage import calculate_coverage
        r = calculate_coverage({"company_name": ""}, "company_profile")
        field = next(f for f in r["fields"] if f["key"] == "company_name")
        assert field["filled"] is False

    def test_whitespace_only_not_filled(self):
        from services.template_field_coverage import calculate_coverage
        r = calculate_coverage({"company_name": "   "}, "company_profile")
        field = next(f for f in r["fields"] if f["key"] == "company_name")
        assert field["filled"] is False

    def test_none_value_not_filled(self):
        from services.template_field_coverage import calculate_coverage
        r = calculate_coverage({"company_name": None}, "company_profile")
        field = next(f for f in r["fields"] if f["key"] == "company_name")
        assert field["filled"] is False

    def test_zero_int_is_filled(self):
        from services.template_field_coverage import calculate_coverage
        # founded_year=0 is unrealistic but treated as filled per impl (only str ""/None empty)
        r = calculate_coverage({"founded_year": 0}, "halal_policy")
        field = next(f for f in r["fields"] if f["key"] == "founded_year")
        assert field["filled"] is True

    def test_field_labels_vi_present(self):
        from services.template_field_coverage import FIELD_LABELS_VI
        assert "halal_commitment_statement" in FIELD_LABELS_VI
        assert FIELD_LABELS_VI["halal_commitment_statement"]  # non-empty

    def test_doc_type_in_response(self):
        from services.template_field_coverage import calculate_coverage
        r = calculate_coverage({}, "halal_policy")
        assert r["doc_type"] == "halal_policy"


# ── Schema migration verification (3 tests) ────────────────────────────────


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def _pool():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    from auth.db import init_pool
    import auth.db as _db
    if _db._pool is None:
        await init_pool()
    yield


@pytest_asyncio.fixture(loop_scope="session")
async def conn(_pool):
    url = os.getenv("DATABASE_URL")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


@pytest_asyncio.fixture(loop_scope="session")
async def client(_pool):
    from app import app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as c:
        yield c


class TestSchemaApplied:
    async def test_users_has_new_columns(self, conn):
        cols = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND table_schema = 'public'
        """)
        names = {r["column_name"] for r in cols}
        for c in ["founded_year", "halal_commitment_statement",
                  "ihc_chairman_name", "production_capacity_brief"]:
            assert c in names, f"Column {c} missing from users table"

    async def test_gcc_standards_seeded(self, conn):
        for code in ("uae_s_2055_1_2015", "gso_2055_2_2021",
                     "oic_smiic_1_2019", "has_23000_2012"):
            row = await conn.fetchrow(
                "SELECT enabled FROM standard_types WHERE code = $1", code,
            )
            assert row is not None, f"Standard {code} not seeded"
            assert row["enabled"] is True

    async def test_existing_users_unaffected(self, conn):
        """Pre-existing users still query without error."""
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        assert count > 0


# ── PATCH /auth/company-profile integration (8 tests) ──────────────────────


@pytest_asyncio.fixture(loop_scope="session")
async def biz_owner(conn):
    row = await conn.fetchrow(
        "SELECT id, email, tenant_id FROM users "
        "WHERE role='business' AND is_owner=true LIMIT 1"
    )
    if not row:
        pytest.skip("Need business owner")
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else str(row["id"]),
    }


def _biz_jwt(user):
    return jwt.encode({
        "sub": user["id"], "email": user["email"], "role": "business",
        "is_owner": True, "tenant_id": user["tenant_id"],
        "exp": time.time() + 3600,
    }, SECRET, algorithm=ALGORITHM)


class TestCompanyProfilePATCH:
    async def test_patch_founded_year_persists(self, client, biz_owner, conn):
        await client.put(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
            json={"founded_year": 2015},
        )
        try:
            row = await conn.fetchrow(
                "SELECT founded_year FROM users WHERE id = $1::uuid",
                biz_owner["id"],
            )
            assert row["founded_year"] == 2015
        finally:
            await conn.execute(
                "UPDATE users SET founded_year = NULL WHERE id = $1::uuid",
                biz_owner["id"],
            )

    async def test_patch_halal_commitment_persists(self, client, biz_owner, conn):
        await client.put(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
            json={"halal_commitment_statement": "Test statement"},
        )
        try:
            row = await conn.fetchrow(
                "SELECT halal_commitment_statement FROM users WHERE id = $1::uuid",
                biz_owner["id"],
            )
            assert row["halal_commitment_statement"] == "Test statement"
        finally:
            await conn.execute(
                "UPDATE users SET halal_commitment_statement = NULL WHERE id = $1::uuid",
                biz_owner["id"],
            )

    async def test_patch_ihc_inception_date_iso(self, client, biz_owner, conn):
        await client.put(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
            json={"ihc_inception_date": "2024-01-15"},
        )
        try:
            row = await conn.fetchrow(
                "SELECT ihc_inception_date FROM users WHERE id = $1::uuid",
                biz_owner["id"],
            )
            assert row["ihc_inception_date"].isoformat() == "2024-01-15"
        finally:
            await conn.execute(
                "UPDATE users SET ihc_inception_date = NULL WHERE id = $1::uuid",
                biz_owner["id"],
            )

    async def test_patch_empty_body_returns_no_changes(self, client, biz_owner):
        r = await client.put(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
            json={},
        )
        assert r.status_code == 200
        body = r.json()
        assert "không có thay đổi" in body["message"].lower() or body.get("updated_fields") == []

    async def test_patch_invalid_field_ignored(self, client, biz_owner):
        """Pydantic strips unknown fields; should not error."""
        r = await client.put(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
            json={"unknown_field_xyz": "value"},
        )
        assert r.status_code == 200

    async def test_patch_unauthorized(self, client):
        r = await client.put(
            "/auth/company-profile",
            json={"founded_year": 2015},
        )
        assert r.status_code == 401

    async def test_patch_non_owner_403(self, client, conn):
        staff = await conn.fetchrow(
            "SELECT id, email, tenant_id FROM users "
            "WHERE role='business' AND is_owner=false LIMIT 1"
        )
        if not staff:
            pytest.skip("Need business staff")
        token = jwt.encode({
            "sub": str(staff["id"]), "email": staff["email"], "role": "business",
            "is_owner": False,
            "tenant_id": str(staff["tenant_id"]) if staff["tenant_id"] else str(staff["id"]),
            "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)
        r = await client.put(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {token}"},
            json={"founded_year": 2015},
        )
        assert r.status_code in (403, 401)

    async def test_patch_multiple_fields_atomic(self, client, biz_owner, conn):
        await client.put(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
            json={
                "founded_year": 2010,
                "total_employees": 50,
                "ihc_chairman_name": "Test Chairman",
            },
        )
        try:
            row = await conn.fetchrow(
                "SELECT founded_year, total_employees, ihc_chairman_name "
                "FROM users WHERE id = $1::uuid",
                biz_owner["id"],
            )
            assert row["founded_year"] == 2010
            assert row["total_employees"] == 50
            assert row["ihc_chairman_name"] == "Test Chairman"
        finally:
            await conn.execute(
                "UPDATE users SET founded_year=NULL, total_employees=NULL, "
                "ihc_chairman_name=NULL WHERE id = $1::uuid",
                biz_owner["id"],
            )


# ── GET /auth/company-profile returns new fields (3 tests) ─────────────────


class TestCompanyProfileGET:
    async def test_get_returns_new_fields_in_shape(self, client, biz_owner):
        r = await client.get(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
        )
        assert r.status_code == 200
        body = r.json()
        for f in ["founded_year", "halal_commitment_statement",
                  "ihc_chairman_name", "production_capacity_brief"]:
            assert f in body

    async def test_get_new_fields_default_null(self, client, biz_owner, conn):
        # Clear fields
        await conn.execute(
            "UPDATE users SET founded_year=NULL, halal_commitment_statement=NULL "
            "WHERE id = $1::uuid",
            biz_owner["id"],
        )
        r = await client.get(
            "/auth/company-profile",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
        )
        body = r.json()
        assert body["founded_year"] is None
        assert body["halal_commitment_statement"] is None

    async def test_get_ihc_date_serializes_iso(self, client, biz_owner, conn):
        await conn.execute(
            "UPDATE users SET ihc_inception_date = '2024-06-15' WHERE id = $1::uuid",
            biz_owner["id"],
        )
        try:
            r = await client.get(
                "/auth/company-profile",
                headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
            )
            body = r.json()
            assert body["ihc_inception_date"] == "2024-06-15"
        finally:
            await conn.execute(
                "UPDATE users SET ihc_inception_date = NULL WHERE id = $1::uuid",
                biz_owner["id"],
            )


# ── GET /api/templates/{doc_type}/placeholder-coverage (8 tests) ───────────


class TestPlaceholderCoverageEndpoint:
    async def test_coverage_endpoint_requires_auth(self, client):
        r = await client.get("/api/templates/halal_policy/placeholder-coverage")
        assert r.status_code == 401

    async def test_coverage_endpoint_business_role_ok(self, client, biz_owner):
        r = await client.get(
            "/api/templates/halal_policy/placeholder-coverage",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
        )
        assert r.status_code == 200

    async def test_coverage_endpoint_provider_403(self, client):
        token = jwt.encode({
            "sub": str(uuid4()), "email": "p@x", "role": "provider",
            "is_owner": True, "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)
        r = await client.get(
            "/api/templates/halal_policy/placeholder-coverage",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    async def test_coverage_response_shape(self, client, biz_owner):
        r = await client.get(
            "/api/templates/halal_policy/placeholder-coverage",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
        )
        body = r.json()
        for key in ("doc_type", "total_fields", "filled", "empty", "coverage_pct", "fields"):
            assert key in body

    async def test_coverage_reflects_data_update(self, client, biz_owner, conn):
        # Clear then update
        await conn.execute(
            "UPDATE users SET halal_commitment_statement = NULL WHERE id = $1::uuid",
            biz_owner["id"],
        )
        r1 = await client.get(
            "/api/templates/halal_policy/placeholder-coverage",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
        )
        pct_empty = r1.json()["coverage_pct"]

        await conn.execute(
            "UPDATE users SET halal_commitment_statement = 'Test' WHERE id = $1::uuid",
            biz_owner["id"],
        )
        try:
            r2 = await client.get(
                "/api/templates/halal_policy/placeholder-coverage",
                headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
            )
            pct_filled = r2.json()["coverage_pct"]
            assert pct_filled > pct_empty
        finally:
            await conn.execute(
                "UPDATE users SET halal_commitment_statement = NULL WHERE id = $1::uuid",
                biz_owner["id"],
            )

    async def test_coverage_unknown_doc_type_identity_only(self, client, biz_owner):
        r = await client.get(
            "/api/templates/unknown_xyz_999/placeholder-coverage",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
        )
        assert r.status_code == 200
        body = r.json()
        # Only 5 identity fields for unknown doc_type
        assert body["total_fields"] == 5

    async def test_coverage_internal_halal_committee_has_ihc_fields(
        self, client, biz_owner,
    ):
        r = await client.get(
            "/api/templates/internal_halal_committee/placeholder-coverage",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
        )
        body = r.json()
        field_keys = [f["key"] for f in body["fields"]]
        assert "ihc_chairman_name" in field_keys
        assert "ihc_meeting_frequency" in field_keys

    async def test_coverage_pct_between_0_and_100(self, client, biz_owner):
        r = await client.get(
            "/api/templates/has_manual/placeholder-coverage",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_owner)}"},
        )
        body = r.json()
        assert 0 <= body["coverage_pct"] <= 100
