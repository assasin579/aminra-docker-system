"""F4 — Dossier CRUD integration tests (30 cases).

Live DB via httpx ASGI. Covers full CRUD lifecycle + cross-tenant scope +
documents FK + standard validation against user's industry mapping.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from jose import jwt

from auth.jwt_utils import SECRET, ALGORITHM

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
async def biz_user_with_industry(conn):
    """Business owner with industry_schema_id set + their available standards."""
    row = await conn.fetchrow("""
        SELECT u.id, u.email, u.tenant_id, u.industry_schema_id
        FROM users u
        WHERE u.role='business' AND u.is_owner=true
          AND u.industry_schema_id IS NOT NULL
        LIMIT 1
    """)
    if not row:
        pytest.skip("Need business owner with industry_schema_id set")

    # Get default standard for this industry
    std = await conn.fetchrow("""
        SELECT st.id, st.code FROM standard_types st
        JOIN industry_standards is_link ON is_link.standard_type_id = st.id
        WHERE is_link.industry_schema_id = $1
        ORDER BY is_link.is_default DESC LIMIT 1
    """, row["industry_schema_id"])
    if not std:
        pytest.skip("Industry has no mapped standards")

    return {
        "user_id": str(row["id"]),
        "email": row["email"],
        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else str(row["id"]),
        "industry_schema_id": str(row["industry_schema_id"]),
        "standard_type_id": str(std["id"]),
        "standard_code": std["code"],
    }


def _biz_jwt(user) -> str:
    return jwt.encode({
        "sub": user["user_id"],
        "email": user["email"],
        "role": "business",
        "is_owner": True,
        "tenant_id": user["tenant_id"],
        "exp": time.time() + 3600,
    }, SECRET, algorithm=ALGORITHM)


@pytest_asyncio.fixture(loop_scope="session")
async def cleanup_test_dossiers(conn):
    """Track + cleanup dossiers created during tests."""
    ids = []
    yield ids
    if ids:
        await conn.execute(
            "DELETE FROM dossiers WHERE id = ANY($1::uuid[])", ids,
        )


# ── Group 1 — Auth gate (4 tests) ──────────────────────────────────────────


class TestAuthGate:
    async def test_list_no_auth_401(self, client):
        r = await client.get("/dossiers")
        assert r.status_code == 401

    async def test_create_no_auth_401(self, client):
        r = await client.post(
            "/dossiers",
            json={"title": "X", "standard_type_id": str(uuid4())},
        )
        assert r.status_code == 401

    async def test_get_detail_no_auth_401(self, client):
        r = await client.get(f"/dossiers/{uuid4()}")
        assert r.status_code == 401

    async def test_create_provider_role_403(self, client, biz_user_with_industry):
        # Sign as provider not business
        token = jwt.encode({
            "sub": str(uuid4()),
            "email": "p@x.com",
            "role": "provider",
            "is_owner": True,
            "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        assert r.status_code == 403


# ── Group 2 — Create flow (6 tests) ────────────────────────────────────────


class TestCreate:
    async def test_create_returns_201_with_id(
        self, client, biz_user_with_industry, cleanup_test_dossiers, conn,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "Integration test dossier",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        assert r.status_code == 201
        body = r.json()
        cleanup_test_dossiers.append(body["id"])
        assert body["title"] == "Integration test dossier"
        assert body["status"] == "draft"
        assert body["standard_code"] == biz_user_with_industry["standard_code"]

    async def test_create_with_notes(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "With notes",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
                "notes": "Pilot CB HCM",
            },
        )
        assert r.status_code == 201
        body = r.json()
        cleanup_test_dossiers.append(body["id"])
        assert body["notes"] == "Pilot CB HCM"

    async def test_create_with_doc_types_populated(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "Has doc types",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        assert r.status_code == 201
        body = r.json()
        cleanup_test_dossiers.append(body["id"])
        assert isinstance(body["doc_types"], list)

    async def test_create_invalid_standard_404(
        self, client, biz_user_with_industry,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "Bad standard",
                "standard_type_id": str(uuid4()),  # nonexistent
            },
        )
        assert r.status_code == 404

    async def test_create_empty_title_422(self, client, biz_user_with_industry):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        assert r.status_code == 422

    async def test_create_long_title_422(self, client, biz_user_with_industry):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "x" * 300,
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        assert r.status_code == 422


# ── Group 3 — Standard validation against industry (3 tests) ───────────────


class TestStandardValidation:
    async def test_standard_not_in_user_industry_400(
        self, client, biz_user_with_industry, conn,
    ):
        """User in food_manufacturing → tries MS 2200 (cosmetic) → 400."""
        # Find a standard NOT mapped to user's industry
        other = await conn.fetchrow("""
            SELECT id FROM standard_types
            WHERE enabled = true
              AND id NOT IN (
                SELECT standard_type_id FROM industry_standards
                WHERE industry_schema_id = $1
              )
            LIMIT 1
        """, biz_user_with_industry["industry_schema_id"])
        if not other:
            pytest.skip("Need ≥1 standard NOT mapped to user's industry")

        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "Wrong standard",
                "standard_type_id": str(other["id"]),
            },
        )
        assert r.status_code == 400

    async def test_disabled_standard_rejected(
        self, client, biz_user_with_industry, conn,
    ):
        """Disabled standard → 404 (treated as not found)."""
        std_id = biz_user_with_industry["standard_type_id"]
        await conn.execute(
            "UPDATE standard_types SET enabled = false WHERE id = $1", std_id,
        )
        try:
            r = await client.post(
                "/dossiers",
                headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
                json={"title": "Disabled std", "standard_type_id": std_id},
            )
            assert r.status_code == 404
        finally:
            await conn.execute(
                "UPDATE standard_types SET enabled = true WHERE id = $1", std_id,
            )

    async def test_standard_in_industry_passes(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "Valid standard",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        assert r.status_code == 201
        cleanup_test_dossiers.append(r.json()["id"])


# ── Group 4 — Cross-tenant isolation (4 tests) ─────────────────────────────


class TestCrossTenantIsolation:
    async def test_list_only_shows_own_tenant(
        self, client, conn, biz_user_with_industry, cleanup_test_dossiers,
    ):
        # Create a dossier as user A
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "Owned by A",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        cleanup_test_dossiers.append(r.json()["id"])

        # Find another tenant
        other = await conn.fetchrow("""
            SELECT id, email, tenant_id FROM users
            WHERE role='business' AND is_owner=true
              AND tenant_id IS DISTINCT FROM $1
            LIMIT 1
        """, biz_user_with_industry["tenant_id"])
        if not other:
            pytest.skip("Need 2 business tenants")

        other_jwt = jwt.encode({
            "sub": str(other["id"]),
            "email": other["email"],
            "role": "business",
            "is_owner": True,
            "tenant_id": str(other["tenant_id"]) if other["tenant_id"] else str(other["id"]),
            "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)

        r2 = await client.get(
            "/dossiers",
            headers={"Authorization": f"Bearer {other_jwt}"},
        )
        assert r2.status_code == 200
        ids = [d["id"] for d in r2.json()]
        assert cleanup_test_dossiers[-1] not in ids

    async def test_other_tenant_get_detail_404(
        self, client, conn, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "private",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        other = await conn.fetchrow("""
            SELECT id, email, tenant_id FROM users
            WHERE role='business' AND is_owner=true
              AND tenant_id IS DISTINCT FROM $1
            LIMIT 1
        """, biz_user_with_industry["tenant_id"])
        if not other:
            pytest.skip("Need 2 business tenants")

        other_jwt = jwt.encode({
            "sub": str(other["id"]),
            "email": other["email"],
            "role": "business",
            "is_owner": True,
            "tenant_id": str(other["tenant_id"]) if other["tenant_id"] else str(other["id"]),
            "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)

        r2 = await client.get(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {other_jwt}"},
        )
        assert r2.status_code == 404

    async def test_other_tenant_patch_404(
        self, client, conn, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "private",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        other = await conn.fetchrow(
            "SELECT id, email, tenant_id FROM users "
            "WHERE role='business' AND is_owner=true "
            "AND tenant_id IS DISTINCT FROM $1 LIMIT 1",
            biz_user_with_industry["tenant_id"],
        )
        if not other:
            pytest.skip("Need 2 business tenants")
        other_jwt = jwt.encode({
            "sub": str(other["id"]), "email": other["email"], "role": "business",
            "is_owner": True,
            "tenant_id": str(other["tenant_id"]) if other["tenant_id"] else str(other["id"]),
            "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)

        r2 = await client.patch(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {other_jwt}"},
            json={"title": "Hijacked"},
        )
        assert r2.status_code == 404

    async def test_other_tenant_delete_silent(
        self, client, conn, biz_user_with_industry, cleanup_test_dossiers,
    ):
        """DELETE with wrong tenant — returns 204 but UPDATE 0 rows; verify."""
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "private",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        other = await conn.fetchrow(
            "SELECT id, email, tenant_id FROM users "
            "WHERE role='business' AND is_owner=true "
            "AND tenant_id IS DISTINCT FROM $1 LIMIT 1",
            biz_user_with_industry["tenant_id"],
        )
        if not other:
            pytest.skip("Need 2 business tenants")
        other_jwt = jwt.encode({
            "sub": str(other["id"]), "email": other["email"], "role": "business",
            "is_owner": True,
            "tenant_id": str(other["tenant_id"]) if other["tenant_id"] else str(other["id"]),
            "exp": time.time() + 3600,
        }, SECRET, algorithm=ALGORITHM)

        r2 = await client.delete(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {other_jwt}"},
        )
        # Endpoint returns 204 regardless (UPDATE matched 0 rows silently)
        assert r2.status_code == 204
        # Verify dossier UNCHANGED
        row = await conn.fetchrow(
            "SELECT status FROM dossiers WHERE id = $1::uuid", dossier_id,
        )
        assert row["status"] != "cancelled"


# ── Group 5 — Lifecycle PATCH + DELETE (5 tests) ───────────────────────────


class TestLifecycle:
    async def test_patch_title(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "Original",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        r2 = await client.patch(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={"title": "Updated"},
        )
        assert r2.status_code == 200
        assert r2.json()["title"] == "Updated"

    async def test_patch_status_transition(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        r2 = await client.patch(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={"status": "in_progress"},
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "in_progress"

    async def test_patch_empty_body_400(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        r2 = await client.patch(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={},
        )
        assert r2.status_code == 400

    async def test_patch_invalid_status_422(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        r2 = await client.patch(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={"status": "approved"},
        )
        assert r2.status_code == 422

    async def test_delete_marks_cancelled_not_remove(
        self, client, conn, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        r2 = await client.delete(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
        )
        assert r2.status_code == 204
        row = await conn.fetchrow(
            "SELECT status FROM dossiers WHERE id = $1::uuid", dossier_id,
        )
        assert row["status"] == "cancelled"


# ── Group 6 — Documents FK (4 tests) ───────────────────────────────────────


class TestDocumentsFKLink:
    async def test_get_detail_includes_documents_field(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        r2 = await client.get(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
        )
        body = r2.json()
        assert "documents" in body
        assert isinstance(body["documents"], list)

    async def test_list_endpoint_omits_documents(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        """List endpoint returns documents=[] (include_documents=False)
        for performance; detail endpoint populates."""
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        cleanup_test_dossiers.append(r.json()["id"])
        r2 = await client.get(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
        )
        for d in r2.json():
            assert d["documents"] == []

    async def test_detail_endpoint_doc_fk_link(
        self, client, conn, biz_user_with_industry, cleanup_test_dossiers,
    ):
        """Insert a document with dossier_id FK + verify appears in detail."""
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        doc_id = uuid4()
        try:
            await conn.execute("""
                INSERT INTO documents
                  (id, tenant_id, user_id, filename, original_filename,
                   file_path, mime_type, file_size, status, dossier_id)
                VALUES ($1, $2, $3, 'doc.pdf', 'doc.pdf', '/x', 'application/pdf',
                        1024, 'uploaded', $4::uuid)
            """, doc_id,
                biz_user_with_industry["tenant_id"],
                biz_user_with_industry["user_id"],
                dossier_id,
            )

            r2 = await client.get(
                f"/dossiers/{dossier_id}",
                headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            )
            doc_ids = [d["id"] for d in r2.json()["documents"]]
            assert str(doc_id) in doc_ids
        finally:
            await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)

    async def test_documents_sorted_uploaded_at_desc(
        self, client, conn, biz_user_with_industry, cleanup_test_dossiers,
    ):
        """Newest uploaded doc first in response."""
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "X",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        doc_old = uuid4()
        doc_new = uuid4()
        try:
            await conn.execute("""
                INSERT INTO documents
                  (id, tenant_id, user_id, filename, original_filename,
                   file_path, mime_type, file_size, status, dossier_id, uploaded_at)
                VALUES ($1, $2, $3, 'old.pdf', 'old.pdf', '/x', 'application/pdf',
                        1024, 'uploaded', $4::uuid, NOW() - INTERVAL '2 days')
            """, doc_old, biz_user_with_industry["tenant_id"],
                biz_user_with_industry["user_id"], dossier_id)
            await conn.execute("""
                INSERT INTO documents
                  (id, tenant_id, user_id, filename, original_filename,
                   file_path, mime_type, file_size, status, dossier_id, uploaded_at)
                VALUES ($1, $2, $3, 'new.pdf', 'new.pdf', '/x', 'application/pdf',
                        1024, 'uploaded', $4::uuid, NOW())
            """, doc_new, biz_user_with_industry["tenant_id"],
                biz_user_with_industry["user_id"], dossier_id)

            r2 = await client.get(
                f"/dossiers/{dossier_id}",
                headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            )
            docs = r2.json()["documents"]
            assert docs[0]["id"] == str(doc_new)
            assert docs[1]["id"] == str(doc_old)
        finally:
            await conn.execute(
                "DELETE FROM documents WHERE id = ANY($1::uuid[])",
                [doc_old, doc_new],
            )


# ── Group 7 — Edge cases (4 tests) ─────────────────────────────────────────


class TestEdgeCases:
    async def test_get_nonexistent_id_404(self, client, biz_user_with_industry):
        r = await client.get(
            f"/dossiers/{uuid4()}",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
        )
        assert r.status_code == 404

    async def test_get_malformed_uuid_422(self, client, biz_user_with_industry):
        r = await client.get(
            "/dossiers/not-a-uuid",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
        )
        assert r.status_code == 422

    async def test_cancelled_dossier_not_in_list(
        self, client, biz_user_with_industry, cleanup_test_dossiers,
    ):
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "TBC",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        dossier_id = r.json()["id"]
        cleanup_test_dossiers.append(dossier_id)

        await client.delete(
            f"/dossiers/{dossier_id}",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
        )
        r2 = await client.get(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
        )
        ids = [d["id"] for d in r2.json()]
        assert dossier_id not in ids

    async def test_audit_log_on_create(
        self, client, conn, biz_user_with_industry, cleanup_test_dossiers,
    ):
        before = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_logs WHERE action = 'dossier_created'"
        )
        r = await client.post(
            "/dossiers",
            headers={"Authorization": f"Bearer {_biz_jwt(biz_user_with_industry)}"},
            json={
                "title": "Audit test",
                "standard_type_id": biz_user_with_industry["standard_type_id"],
            },
        )
        cleanup_test_dossiers.append(r.json()["id"])
        after = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_logs WHERE action = 'dossier_created'"
        )
        assert after == before + 1
