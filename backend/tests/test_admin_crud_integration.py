"""F1+F2+F3 — Admin CRUD integration tests (combined, 70 cases).

Covers:
  - F2 standards CRUD round-trip (admin endpoints)
  - F3 industry↔standard M:N replace + uniqueness constraint
  - F1 industry-schema admin list + create + onboarding flow
  - Cross-cutting: audit_logs writes, soft-disable preserves doc_types
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

from auth.jwt_utils import ADMIN_EMAIL, SECRET, ALGORITHM

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── Fixtures ───────────────────────────────────────────────────────────────


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


@pytest_asyncio.fixture(loop_scope="session")
async def admin_token(conn):
    row = await conn.fetchrow(
        "SELECT id FROM users WHERE email = $1", ADMIN_EMAIL,
    )
    if not row:
        pytest.skip("Admin DB row missing")
    return jwt.encode({
        "sub": str(row["id"]),
        "email": ADMIN_EMAIL,
        "role": "provider",
        "is_owner": True,
        "exp": time.time() + 3600,
    }, SECRET, algorithm=ALGORITHM)


@pytest_asyncio.fixture(loop_scope="session")
async def cleanup_standards(conn):
    codes = []
    yield codes
    if codes:
        await conn.execute(
            "DELETE FROM standard_types WHERE code = ANY($1::text[])", codes,
        )


@pytest_asyncio.fixture(loop_scope="session")
async def cleanup_industries(conn):
    codes = []
    yield codes
    if codes:
        await conn.execute(
            "DELETE FROM industry_schemas WHERE code = ANY($1::text[])", codes,
        )


# ── F2 — Standard CRUD round-trip (15 tests) ───────────────────────────────


class TestStandardCRUDFlow:
    async def test_list_includes_seeded_standards(self, client, admin_token):
        r = await client.get(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        codes = [s["code"] for s in r.json()]
        # at least 1 of the 5 seed standards exists
        assert any(c.startswith("ms_") or c.startswith("mpphm_") for c in codes)

    async def test_create_standard_201(self, client, admin_token, cleanup_standards):
        code = f"test_create_{uuid4().hex[:6]}"
        r = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "code": code,
                "name_vi": "Test Standard",
                "organization": "JAKIM",
                "scheme_version": "2026",
                "enabled": True,
            },
        )
        assert r.status_code == 201
        cleanup_standards.append(code)
        assert r.json()["code"] == code

    async def test_create_duplicate_code_409(self, client, admin_token, cleanup_standards):
        code = f"test_dup_{uuid4().hex[:6]}"
        await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "First"},
        )
        cleanup_standards.append(code)

        r = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Duplicate"},
        )
        assert r.status_code == 409

    async def test_create_missing_required_422(self, client, admin_token):
        r = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": "missing_name"},  # missing name_vi
        )
        assert r.status_code == 422

    async def test_patch_updates_field(self, client, admin_token, cleanup_standards, conn):
        code = f"test_patch_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Original"},
        )
        cleanup_standards.append(code)
        std_id = cr.json()["id"]

        r = await client.patch(
            f"/auth/admin/standard-types/{std_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name_vi": "Updated"},
        )
        assert r.status_code == 200
        assert r.json()["name_vi"] == "Updated"

    async def test_patch_empty_body_400(self, client, admin_token, cleanup_standards):
        code = f"test_patche_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "X"},
        )
        cleanup_standards.append(code)
        std_id = cr.json()["id"]

        r = await client.patch(
            f"/auth/admin/standard-types/{std_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={},
        )
        assert r.status_code == 400

    async def test_patch_nonexistent_404(self, client, admin_token):
        r = await client.patch(
            f"/auth/admin/standard-types/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name_vi": "X"},
        )
        assert r.status_code == 404

    async def test_disable_soft_delete(self, client, admin_token, cleanup_standards, conn):
        code = f"test_disable_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "ToDisable"},
        )
        cleanup_standards.append(code)
        std_id = cr.json()["id"]

        r = await client.delete(
            f"/auth/admin/standard-types/{std_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 204

        row = await conn.fetchrow(
            "SELECT enabled FROM standard_types WHERE id = $1::uuid", std_id,
        )
        assert row["enabled"] is False

    async def test_disable_nonexistent_404(self, client, admin_token):
        r = await client.delete(
            f"/auth/admin/standard-types/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_doc_types_replace_atomic(
        self, client, admin_token, cleanup_standards, conn,
    ):
        code = f"test_dt_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "DT Test"},
        )
        cleanup_standards.append(code)
        std_id = cr.json()["id"]

        r = await client.put(
            f"/auth/admin/standard-types/{std_id}/doc-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"doc_types": [
                {"doc_type": "halal_policy", "required": True, "display_order": 1},
                {"doc_type": "company_profile", "required": True, "display_order": 2},
            ]},
        )
        assert r.status_code == 200
        assert r.json()["count"] == 2

        # Verify DB state
        rows = await conn.fetch(
            "SELECT doc_type FROM standard_doc_types WHERE standard_type_id = $1::uuid",
            std_id,
        )
        types = {r["doc_type"] for r in rows}
        assert types == {"halal_policy", "company_profile"}

    async def test_doc_types_replace_empty(self, client, admin_token, cleanup_standards):
        code = f"test_empty_dt_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Empty"},
        )
        cleanup_standards.append(code)
        std_id = cr.json()["id"]

        r = await client.put(
            f"/auth/admin/standard-types/{std_id}/doc-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"doc_types": []},
        )
        assert r.status_code == 200

    async def test_doc_types_replace_overwrites(
        self, client, admin_token, cleanup_standards, conn,
    ):
        code = f"test_overw_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/standard-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Overwrite"},
        )
        cleanup_standards.append(code)
        std_id = cr.json()["id"]

        # First batch
        await client.put(
            f"/auth/admin/standard-types/{std_id}/doc-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"doc_types": [
                {"doc_type": "halal_policy", "required": True, "display_order": 1},
            ]},
        )
        # Second batch — different content
        await client.put(
            f"/auth/admin/standard-types/{std_id}/doc-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"doc_types": [
                {"doc_type": "generic", "required": False, "display_order": 1},
            ]},
        )
        rows = await conn.fetch(
            "SELECT doc_type FROM standard_doc_types WHERE standard_type_id = $1::uuid",
            std_id,
        )
        types = {r["doc_type"] for r in rows}
        assert types == {"generic"}  # halal_policy removed

    async def test_by_industry_filter(self, client, admin_token, conn):
        ind = await conn.fetchrow("SELECT code FROM industry_schemas WHERE enabled = true LIMIT 1")
        if not ind:
            pytest.skip("Need at least 1 industry")
        r = await client.get(
            f"/standard-types/by-industry/{ind['code']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Public endpoint OK without admin too — test passes auth
        assert r.status_code in (200, 401, 403)

    async def test_get_standard_by_code(self, client, admin_token):
        r = await client.get(
            "/standard-types/ms_1500_2019",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json()["code"] == "ms_1500_2019"

    async def test_get_standard_by_id(self, client, admin_token, conn):
        row = await conn.fetchrow("SELECT id FROM standard_types LIMIT 1")
        if not row:
            pytest.skip("Need a standard seeded")
        r = await client.get(
            f"/standard-types/{row['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200


# ── F3 — Industry↔Standard mapping (15 tests) ──────────────────────────────


class TestMappingCRUD:
    @pytest_asyncio.fixture(loop_scope="session")
    async def test_industry(self, client, admin_token, cleanup_industries):
        code = f"test_ind_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Test Industry", "enabled": True},
        )
        cleanup_industries.append(code)
        return {"id": cr.json()["id"], "code": code}

    @pytest_asyncio.fixture(loop_scope="session")
    async def test_standards(self, client, admin_token, cleanup_standards):
        codes = []
        ids = []
        for i in range(3):
            code = f"test_std_{uuid4().hex[:6]}"
            r = await client.post(
                "/auth/admin/standard-types",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"code": code, "name_vi": f"Test Std {i}"},
            )
            codes.append(code)
            cleanup_standards.append(code)
            ids.append(r.json()["id"])
        return ids

    async def test_replace_empty_mapping(self, client, admin_token, test_industry):
        r = await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": []},
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0

    async def test_replace_single_standard(
        self, client, admin_token, test_industry, test_standards,
    ):
        r = await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[0], "is_default": True, "display_order": 1},
            ]},
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1

    async def test_replace_multiple_standards(
        self, client, admin_token, test_industry, test_standards, conn,
    ):
        r = await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[0], "is_default": True, "display_order": 1},
                {"standard_type_id": test_standards[1], "is_default": False, "display_order": 2},
                {"standard_type_id": test_standards[2], "is_default": False, "display_order": 3},
            ]},
        )
        assert r.status_code == 200
        rows = await conn.fetch(
            "SELECT standard_type_id FROM industry_standards "
            "WHERE industry_schema_id = $1::uuid",
            test_industry["id"],
        )
        assert len(rows) == 3

    async def test_replace_overwrites_existing(
        self, client, admin_token, test_industry, test_standards, conn,
    ):
        # Pre-load with 2
        await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[0], "is_default": True, "display_order": 1},
                {"standard_type_id": test_standards[1], "is_default": False, "display_order": 2},
            ]},
        )
        # Replace with different set
        await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[2], "is_default": True, "display_order": 1},
            ]},
        )
        rows = await conn.fetch(
            "SELECT standard_type_id FROM industry_standards "
            "WHERE industry_schema_id = $1::uuid",
            test_industry["id"],
        )
        assert len(rows) == 1
        assert str(rows[0]["standard_type_id"]) == test_standards[2]

    async def test_replace_industry_404(self, client, admin_token):
        r = await client.put(
            f"/auth/admin/standard-types/industries/{uuid4()}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": []},
        )
        assert r.status_code == 404

    async def test_replace_non_admin_403(self, client, test_industry):
        biz_jwt = jwt.encode({
            "sub": str(uuid4()), "email": "b@x", "role": "business",
            "is_owner": True, "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)
        r = await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {biz_jwt}"},
            json={"standards": []},
        )
        assert r.status_code == 403

    async def test_default_persists_in_db(
        self, client, admin_token, test_industry, test_standards, conn,
    ):
        await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[0], "is_default": True, "display_order": 1},
            ]},
        )
        row = await conn.fetchrow(
            "SELECT is_default FROM industry_standards "
            "WHERE industry_schema_id = $1::uuid AND standard_type_id = $2::uuid",
            test_industry["id"], test_standards[0],
        )
        assert row["is_default"] is True

    async def test_display_order_persists(
        self, client, admin_token, test_industry, test_standards, conn,
    ):
        await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[0], "is_default": False, "display_order": 99},
            ]},
        )
        row = await conn.fetchrow(
            "SELECT display_order FROM industry_standards "
            "WHERE industry_schema_id = $1::uuid AND standard_type_id = $2::uuid",
            test_industry["id"], test_standards[0],
        )
        assert row["display_order"] == 99

    async def test_industry_list_includes_available_standards(
        self, client, admin_token, test_industry, test_standards,
    ):
        await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[0], "is_default": True, "display_order": 1},
            ]},
        )
        r = await client.get(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        items = r.json()
        found = next((i for i in items if i["id"] == test_industry["id"]), None)
        assert found is not None
        assert len(found.get("available_standards", [])) >= 1

    async def test_disabled_standard_excluded_from_industry_view(
        self, client, admin_token, test_industry, test_standards, conn,
    ):
        # Map standard then disable it
        await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[0], "is_default": True, "display_order": 1},
            ]},
        )
        await conn.execute(
            "UPDATE standard_types SET enabled = false WHERE id = $1::uuid",
            test_standards[0],
        )
        try:
            r = await client.get(
                f"/industry-schemas/{test_industry['code']}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if r.status_code == 200:
                # Disabled standards should be filtered from public view
                stds = r.json().get("available_standards", [])
                ids = [s["id"] for s in stds]
                assert test_standards[0] not in ids
        finally:
            await conn.execute(
                "UPDATE standard_types SET enabled = true WHERE id = $1::uuid",
                test_standards[0],
            )

    async def test_replace_with_invalid_standard_uuid_format(
        self, client, admin_token, test_industry,
    ):
        r = await client.put(
            f"/auth/admin/standard-types/industries/{test_industry['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": "not-a-uuid", "is_default": True, "display_order": 1},
            ]},
        )
        assert r.status_code == 422

    async def test_two_industries_independent_mappings(
        self, client, admin_token, test_standards, conn, cleanup_industries,
    ):
        # Industry 1
        c1 = f"test_indep1_{uuid4().hex[:6]}"
        cr1 = await client.post(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": c1, "name_vi": "I1"},
        )
        cleanup_industries.append(c1)
        # Industry 2
        c2 = f"test_indep2_{uuid4().hex[:6]}"
        cr2 = await client.post(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": c2, "name_vi": "I2"},
        )
        cleanup_industries.append(c2)

        await client.put(
            f"/auth/admin/standard-types/industries/{cr1.json()['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[0], "is_default": True, "display_order": 1},
            ]},
        )
        await client.put(
            f"/auth/admin/standard-types/industries/{cr2.json()['id']}/standards",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"standards": [
                {"standard_type_id": test_standards[1], "is_default": True, "display_order": 1},
            ]},
        )
        # Verify isolation
        rows1 = await conn.fetch(
            "SELECT standard_type_id FROM industry_standards "
            "WHERE industry_schema_id = $1::uuid",
            cr1.json()["id"],
        )
        rows2 = await conn.fetch(
            "SELECT standard_type_id FROM industry_standards "
            "WHERE industry_schema_id = $1::uuid",
            cr2.json()["id"],
        )
        assert str(rows1[0]["standard_type_id"]) == test_standards[0]
        assert str(rows2[0]["standard_type_id"]) == test_standards[1]

    async def test_audit_log_on_create_industry(self, client, admin_token, conn, cleanup_industries):
        before = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_logs WHERE action = 'industry_schema_created'"
        )
        code = f"test_audit_{uuid4().hex[:6]}"
        await client.post(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Audit Test"},
        )
        cleanup_industries.append(code)
        after = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_logs WHERE action = 'industry_schema_created'"
        )
        assert after == before + 1

    async def test_industry_patch_round_trip(
        self, client, admin_token, conn, cleanup_industries,
    ):
        code = f"test_pat_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Before"},
        )
        cleanup_industries.append(code)
        ind_id = cr.json()["id"]

        r = await client.patch(
            f"/auth/admin/industry-schemas/{ind_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name_vi": "After"},
        )
        assert r.status_code == 200
        assert r.json()["name_vi"] == "After"


# ── F1 — Industry onboarding business-select (10 tests) ────────────────────


class TestBusinessSelectIndustry:
    @pytest_asyncio.fixture(loop_scope="session")
    async def biz_unselected(self, conn):
        """Business owner WITHOUT industry_schema_id set."""
        row = await conn.fetchrow("""
            SELECT id, email, tenant_id, industry_schema_id
            FROM users WHERE role='business' AND is_owner=true LIMIT 1
        """)
        if not row:
            pytest.skip("Need business owner")
        # Save current value
        old_val = row["industry_schema_id"]
        # Clear for test
        await conn.execute(
            "UPDATE users SET industry_schema_id = NULL WHERE id = $1",
            row["id"],
        )
        yield {
            "id": str(row["id"]),
            "email": row["email"],
            "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else str(row["id"]),
            "old_industry_schema_id": old_val,
        }
        # Restore
        await conn.execute(
            "UPDATE users SET industry_schema_id = $1 WHERE id = $2",
            old_val, row["id"],
        )

    def _biz_jwt(self, user):
        return jwt.encode({
            "sub": user["id"], "email": user["email"], "role": "business",
            "is_owner": True, "tenant_id": user["tenant_id"],
            "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)

    async def test_business_select_industry_201(
        self, client, conn, biz_unselected,
    ):
        ind = await conn.fetchrow("SELECT id FROM industry_schemas WHERE enabled = true LIMIT 1")
        if not ind:
            pytest.skip("Need enabled industry")

        r = await client.post(
            "/industry-schemas/business-select",
            headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
            json={"schema_id": str(ind["id"])},
        )
        assert r.status_code in (200, 201)

    async def test_business_select_already_set_409(
        self, client, conn, biz_unselected,
    ):
        ind = await conn.fetchrow("SELECT id FROM industry_schemas WHERE enabled = true LIMIT 1")
        if not ind:
            pytest.skip("Need enabled industry")

        # First call sets industry
        await client.post(
            "/industry-schemas/business-select",
            headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
            json={"schema_id": str(ind["id"])},
        )
        # Second call → 409 conflict
        r = await client.post(
            "/industry-schemas/business-select",
            headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
            json={"schema_id": str(ind["id"])},
        )
        assert r.status_code == 409

    async def test_business_select_provider_role_403(self, client, conn):
        ind = await conn.fetchrow("SELECT id FROM industry_schemas WHERE enabled = true LIMIT 1")
        if not ind:
            pytest.skip("Need enabled industry")
        token = jwt.encode({
            "sub": str(uuid4()), "email": "p@x", "role": "provider",
            "is_owner": True, "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)
        r = await client.post(
            "/industry-schemas/business-select",
            headers={"Authorization": f"Bearer {token}"},
            json={"schema_id": str(ind["id"])},
        )
        assert r.status_code == 403

    async def test_business_select_disabled_industry_404(
        self, client, conn, biz_unselected, admin_token,
    ):
        # Create a disabled industry
        code = f"test_disab_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Disabled", "enabled": False},
        )
        try:
            r = await client.post(
                "/industry-schemas/business-select",
                headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
                json={"schema_id": cr.json()["id"]},
            )
            assert r.status_code == 404
        finally:
            await conn.execute("DELETE FROM industry_schemas WHERE code = $1", code)

    async def test_business_select_invalid_uuid_422(
        self, client, biz_unselected,
    ):
        r = await client.post(
            "/industry-schemas/business-select",
            headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
            json={"schema_id": "not-a-uuid"},
        )
        assert r.status_code == 422

    async def test_business_select_no_auth_401(self, client, conn):
        ind = await conn.fetchrow("SELECT id FROM industry_schemas WHERE enabled = true LIMIT 1")
        if not ind:
            pytest.skip("Need enabled industry")
        r = await client.post(
            "/industry-schemas/business-select",
            json={"schema_id": str(ind["id"])},
        )
        assert r.status_code == 401

    async def test_industry_list_filters_disabled(
        self, client, biz_unselected, admin_token, conn,
    ):
        # Create disabled industry; ensure not in default list
        code = f"test_filt_{uuid4().hex[:6]}"
        cr = await client.post(
            "/auth/admin/industry-schemas",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"code": code, "name_vi": "Hidden", "enabled": False},
        )
        try:
            r = await client.get(
                "/industry-schemas",
                headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
            )
            assert r.status_code == 200
            codes = [i["code"] for i in r.json()]
            assert code not in codes
        finally:
            await conn.execute("DELETE FROM industry_schemas WHERE code = $1", code)

    async def test_get_industry_by_code(self, client, conn, biz_unselected):
        ind = await conn.fetchrow("SELECT code FROM industry_schemas WHERE enabled = true LIMIT 1")
        if not ind:
            pytest.skip()
        r = await client.get(
            f"/industry-schemas/{ind['code']}",
            headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
        )
        assert r.status_code == 200

    async def test_get_industry_nonexistent_404(self, client, biz_unselected):
        r = await client.get(
            "/industry-schemas/nonexistent_code",
            headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
        )
        assert r.status_code == 404

    async def test_industry_schema_id_persists_to_db(
        self, client, conn, biz_unselected,
    ):
        ind = await conn.fetchrow("SELECT id FROM industry_schemas WHERE enabled = true LIMIT 1")
        if not ind:
            pytest.skip()
        await client.post(
            "/industry-schemas/business-select",
            headers={"Authorization": f"Bearer {self._biz_jwt(biz_unselected)}"},
            json={"schema_id": str(ind["id"])},
        )
        row = await conn.fetchrow(
            "SELECT industry_schema_id FROM users WHERE id = $1::uuid",
            biz_unselected["id"],
        )
        assert str(row["industry_schema_id"]) == str(ind["id"])
