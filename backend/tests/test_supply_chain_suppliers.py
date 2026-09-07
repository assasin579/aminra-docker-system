"""Full-coverage test suite for the supplier CRUD lifecycle (50 cases).

Covers:
- Happy path variants
- Required + optional field validation
- Format validation (email, phone, tax_code)
- Length boundaries (DB column limits + Pydantic constraints)
- Multi-tenant isolation (cross-tenant CRUD blocked)
- Role gating (provider rejected)
- Special chars (VN diacritics, emoji, em-dash, SQL injection, XSS payloads)
- Edge cases (null vs empty, leading zeros)
- Status enum + lifecycle
- Cascade / referential integrity (delete with materials/certificates)
- 404 paths (get/update/delete missing IDs)

Tests run inside an outer transaction (fixture `db_tx`) that rolls back at
teardown so the dev DB is never polluted.
"""
from __future__ import annotations

from uuid import uuid4
from typing import Any, cast

import pytest
from fastapi import HTTPException

from supply_chain.models import SupplierCreate, SupplierUpdate
from supply_chain.supplier_router import (
    create_supplier,
    delete_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
    view_certificate,
)


# ─── helpers ─────────────────────────────────────────────────────────────────


async def _create(db, user, **kwargs):
    """Wrapper so each test can call _create(db, biz_a, name="X") concisely."""
    payload = {"name": kwargs.pop("name", f"Supplier {uuid4().hex[:6]}"), **kwargs}
    return await create_supplier(req=SupplierCreate(**payload), user=user, db=db)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1: HAPPY PATH (5 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHappyPath:
    async def test_01_full_payload(self, db_tx, biz_a):
        result = await _create(
            db_tx, biz_a,
            name="Cty TNHH Halal Việt",
            address="123 Lê Lợi, Q1, TP.HCM",
            phone="0901234567",
            email="contact@halalviet.vn",
            contact_person="Nguyễn Văn A",
            supplier_type="ingredient",
            tax_code="0312345678",
            notes="Đối tác chiến lược",
        )
        assert "id" in result and result["message"] == "Đã tạo nhà cung cấp"

    async def test_02_minimal_only_name(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="Min Supplier")
        assert "id" in r

    async def test_03_typical_fields(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="Typical", email="x@y.vn", phone="0987654321")
        assert "id" in r

    async def test_04_tax_code_10_digits_individual(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="Cá nhân", tax_code="0123456789")
        sid = r["id"]
        row = await db_tx.fetchrow("SELECT tax_code FROM suppliers WHERE id=$1", sid)
        assert row["tax_code"] == "0123456789"

    async def test_05_tax_code_13_digits_branch(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="DN có CN", tax_code="0312345678-001")
        row = await db_tx.fetchrow("SELECT tax_code FROM suppliers WHERE id=$1", r["id"])
        assert row["tax_code"] == "0312345678-001"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2: REQUIRED FIELD VALIDATION (3 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequiredFields:
    async def test_06_missing_name_pydantic_rejects(self, db_tx, biz_a):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SupplierCreate()  # name required

    async def test_07_empty_string_name_rejected(self, db_tx, biz_a):
        # Pydantic min_length=1 + non-blank validator now reject empty.
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            await _create(db_tx, biz_a, name="")

    async def test_08_whitespace_only_name_rejected(self, db_tx, biz_a):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            await _create(db_tx, biz_a, name="   ")


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3: FIELD FORMAT (8 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFieldFormat:
    async def test_09_invalid_email_rejected(self, db_tx, biz_a):
        # Pydantic EmailStr now enforces RFC 5322-ish format at API boundary.
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            await _create(db_tx, biz_a, name="email_invalid", email="not-an-email")

    async def test_10_email_with_vn_subdomain(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="vn email", email="lien.he@congty.com.vn")
        assert "id" in r

    async def test_11_phone_too_short_currently_accepted(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="ph short", phone="123")
        assert "id" in r

    async def test_12_phone_with_country_code(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="ph cc", phone="+84901234567")
        assert "id" in r

    async def test_13_phone_max_50_chars(self, db_tx, biz_a):
        # phone column is varchar(50)
        r = await _create(db_tx, biz_a, name="ph max", phone="0" * 50)
        assert "id" in r

    async def test_14_phone_over_50_rejected_by_db(self, db_tx, biz_a):
        with pytest.raises(Exception):  # asyncpg DataError or similar
            await _create(db_tx, biz_a, name="ph over", phone="0" * 51)

    async def test_15_tax_code_with_letters_rejected(self, db_tx, biz_a):
        # VN tax code regex now enforces digits-only (10 or 10-3 format).
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            await _create(db_tx, biz_a, name="tc letters", tax_code="ABC1234567")

    async def test_16_tax_code_over_20_chars_rejected_by_db(self, db_tx, biz_a):
        with pytest.raises(Exception):
            await _create(db_tx, biz_a, name="tc over", tax_code="1" * 21)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4: LENGTH BOUNDARIES (5 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLengthBoundaries:
    async def test_17_name_exactly_255_ok(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="x" * 255)
        assert "id" in r

    async def test_18_name_256_db_rejects(self, db_tx, biz_a):
        with pytest.raises(Exception):
            await _create(db_tx, biz_a, name="x" * 256)

    async def test_19_address_5000_chars_ok_text_column(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="long addr", address="A" * 5000)
        assert "id" in r

    async def test_20_notes_50000_chars_ok(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="long notes", notes="N" * 50000)
        assert "id" in r

    async def test_21_contact_person_256_db_rejects(self, db_tx, biz_a):
        with pytest.raises(Exception):
            await _create(db_tx, biz_a, name="cp over", contact_person="P" * 256)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5: MULTI-TENANT ISOLATION (4 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiTenantIsolation:
    async def test_22_biz_b_does_not_see_biz_a_supplier_in_list(self, db_tx, biz_a, biz_b):
        await _create(db_tx, biz_a, name="A's secret supplier")
        result = await list_suppliers(status=None, user=biz_b, db=db_tx)
        names = [s.name for s in result["suppliers"]]
        assert "A's secret supplier" not in names

    async def test_23_biz_b_get_by_id_404(self, db_tx, biz_a, biz_b):
        r = await _create(db_tx, biz_a, name="A only")
        with pytest.raises(HTTPException) as exc:
            await get_supplier(sid=r["id"], user=biz_b, db=db_tx)
        assert exc.value.status_code == 404

    async def test_24_biz_b_update_404(self, db_tx, biz_a, biz_b):
        r = await _create(db_tx, biz_a, name="A only upd")
        with pytest.raises(HTTPException) as exc:
            await update_supplier(
                sid=r["id"],
                req=SupplierUpdate(name="hacked"),
                user=biz_b, db=db_tx,
            )
        assert exc.value.status_code == 404

    async def test_25_biz_b_delete_404(self, db_tx, biz_a, biz_b):
        r = await _create(db_tx, biz_a, name="A only del")
        with pytest.raises(HTTPException) as exc:
            await delete_supplier(sid=r["id"], user=biz_b, db=db_tx)
        assert exc.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6: ROLE GATING (4 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoleGating:
    async def test_26_provider_cannot_create(self, db_tx, prov_user):
        with pytest.raises(HTTPException) as exc:
            await _create(db_tx, prov_user, name="hostile")
        assert exc.value.status_code == 403

    async def test_27_provider_cannot_list(self, db_tx, prov_user):
        with pytest.raises(HTTPException) as exc:
            await list_suppliers(status=None, user=prov_user, db=db_tx)
        assert exc.value.status_code == 403

    async def test_28_provider_cannot_update(self, db_tx, prov_user, biz_a):
        r = await _create(db_tx, biz_a, name="update target")
        with pytest.raises(HTTPException) as exc:
            await update_supplier(
                sid=r["id"], req=SupplierUpdate(name="hacked"),
                user=prov_user, db=db_tx,
            )
        assert exc.value.status_code == 403

    async def test_29_provider_cannot_delete(self, db_tx, prov_user, biz_a):
        r = await _create(db_tx, biz_a, name="del target")
        with pytest.raises(HTTPException) as exc:
            await delete_supplier(sid=r["id"], user=prov_user, db=db_tx)
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7: SPECIAL CHARS / SECURITY (5 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpecialChars:
    async def test_30_vn_diacritics_preserved(self, db_tx, biz_a):
        name = "Cty TNHH Hải Đăng Nguyễn"
        r = await _create(db_tx, biz_a, name=name)
        row = await db_tx.fetchrow("SELECT name FROM suppliers WHERE id=$1", r["id"])
        assert row["name"] == name

    async def test_31_emoji_in_name(self, db_tx, biz_a):
        name = "🌟 Halal Star ✨"
        r = await _create(db_tx, biz_a, name=name)
        row = await db_tx.fetchrow("SELECT name FROM suppliers WHERE id=$1", r["id"])
        assert row["name"] == name

    async def test_32_em_dash(self, db_tx, biz_a):
        name = "Cty A — Halal"  # em-dash
        r = await _create(db_tx, biz_a, name=name)
        row = await db_tx.fetchrow("SELECT name FROM suppliers WHERE id=$1", r["id"])
        assert row["name"] == name

    async def test_33_sql_injection_attempt_safe(self, db_tx, biz_a):
        # asyncpg uses parameterised queries → injection should be stored as
        # literal text, not executed. Validate suppliers table still intact.
        name = "'; DROP TABLE suppliers;--"
        r = await _create(db_tx, biz_a, name=name)
        row = await db_tx.fetchrow("SELECT name FROM suppliers WHERE id=$1", r["id"])
        assert row["name"] == name
        # Sanity: table still queryable
        await db_tx.fetchval("SELECT COUNT(*) FROM suppliers")

    async def test_34_xss_payload_stored_verbatim(self, db_tx, biz_a):
        # XSS prevention is the FE's job — backend stores the raw payload.
        notes = "<script>alert('xss')</script>"
        r = await _create(db_tx, biz_a, name="xss test", notes=notes)
        row = await db_tx.fetchrow("SELECT notes FROM suppliers WHERE id=$1", r["id"])
        assert row["notes"] == notes


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8: EDGE CASES (5 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    async def test_35_all_optional_fields_omitted(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="bare")
        row = await db_tx.fetchrow(
            "SELECT address, phone, email, contact_person, supplier_type, tax_code, notes "
            "FROM suppliers WHERE id=$1", r["id"]
        )
        assert all(row[k] is None for k in row.keys())

    async def test_36_tax_code_leading_zero_preserved(self, db_tx, biz_a):
        # Critical: tax_code is text not integer; leading zeros must survive.
        r = await _create(db_tx, biz_a, name="lz", tax_code="0001234567")
        row = await db_tx.fetchrow("SELECT tax_code FROM suppliers WHERE id=$1", r["id"])
        assert row["tax_code"] == "0001234567"

    async def test_37_empty_string_vs_null_kept_distinct(self, db_tx, biz_a):
        # Pydantic Optional[str] = None default — but if FE explicitly sends "",
        # the value is "" not None. Backend currently writes the empty string.
        r = await _create(db_tx, biz_a, name="es", notes="")
        row = await db_tx.fetchrow("SELECT notes FROM suppliers WHERE id=$1", r["id"])
        assert row["notes"] == ""

    async def test_38_supplier_type_arbitrary_value_accepted(self, db_tx, biz_a):
        # supplier_type is varchar(100) without enum / FK. Accepts anything <=100.
        # FLAG for product: should probably be enum (ingredient | packaging |
        # service | other) for cert workflow consistency.
        r = await _create(db_tx, biz_a, name="t arb", supplier_type="weird-novel-type-xyz")
        assert "id" in r

    async def test_39_two_suppliers_same_name_same_tenant_both_succeed(self, db_tx, biz_a):
        # No unique constraint. Test that this design choice is intentional —
        # business user might genuinely have 2 distinct suppliers with same legal
        # name (different addresses / branches).
        a = await _create(db_tx, biz_a, name="Duplicate Name Co")
        b = await _create(db_tx, biz_a, name="Duplicate Name Co")
        assert a["id"] != b["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9: STATUS LIFECYCLE (4 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusLifecycle:
    async def test_40_default_status_pending_on_create(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="status default")
        row = await db_tx.fetchrow("SELECT status FROM suppliers WHERE id=$1", r["id"])
        assert row["status"] == "pending"

    async def test_41_business_cannot_self_mark_supplier_verified(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="st verified")
        with pytest.raises(HTTPException) as exc:
            await update_supplier(
                sid=r["id"], req=SupplierUpdate(status="verified"),
                user=biz_a, db=db_tx,
            )
        assert exc.value.status_code == 400
        assert "CB" in str(exc.value.detail)
        row = await db_tx.fetchrow("SELECT status FROM suppliers WHERE id=$1", r["id"])
        assert row["status"] == "pending"

    async def test_42_business_can_mark_supplier_suspended_as_local_operational_hold(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="st suspended")
        await update_supplier(
            sid=r["id"], req=SupplierUpdate(status="suspended"),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT status FROM suppliers WHERE id=$1", r["id"])
        assert row["status"] == "suspended"

    async def test_43_invalid_status_rejected_by_db_enum(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="bad st")
        with pytest.raises(Exception):
            await update_supplier(
                sid=r["id"], req=SupplierUpdate(status="not_a_real_status"),
                user=biz_a, db=db_tx,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 10: CASCADE / REFERENTIAL INTEGRITY (4 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCascade:
    async def test_44_delete_no_dependents_succeeds(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="standalone")
        result = await delete_supplier(sid=r["id"], user=biz_a, db=db_tx)
        assert "message" in result or "id" in result or result is None
        gone = await db_tx.fetchrow("SELECT id FROM suppliers WHERE id=$1", r["id"])
        assert gone is None

    async def test_45_delete_with_material_blocked_by_fk(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="has materials")
        # Insert dependent material directly (skip material router auth path)
        await db_tx.execute(
            "INSERT INTO materials (id, tenant_id, supplier_id, name) "
            "VALUES ($1::uuid, $2::uuid, $3::uuid, $4)",
            uuid4(), biz_a["tenant_id"], r["id"], "blocking_mat",
        )
        with pytest.raises(Exception):  # FK violation OR API 409
            await delete_supplier(sid=r["id"], user=biz_a, db=db_tx)

    async def test_46_delete_with_certificate_cascades(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="has certs")
        cert_id = uuid4()
        await db_tx.execute(
            "INSERT INTO supplier_certificates (id, supplier_id, tenant_id, cert_type, file_path) "
            "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5)",
            cert_id, r["id"], biz_a["tenant_id"], "halal", "/tmp/fake.pdf",
        )
        await delete_supplier(sid=r["id"], user=biz_a, db=db_tx)
        cert_gone = await db_tx.fetchrow(
            "SELECT id FROM supplier_certificates WHERE id=$1", cert_id
        )
        assert cert_gone is None  # ON DELETE CASCADE

    async def test_47_supplier_deleted_does_not_appear_in_list(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="ghost")
        await delete_supplier(sid=r["id"], user=biz_a, db=db_tx)
        listing = await list_suppliers(status=None, user=biz_a, db=db_tx)
        ids = [s.id for s in listing["suppliers"]]
        assert r["id"] not in ids


# ═══════════════════════════════════════════════════════════════════════════════
# Group 11: 404 PATHS (3 cases)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotFound:
    async def test_48_get_missing_404(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await get_supplier(sid=str(uuid4()), user=biz_a, db=db_tx)
        assert exc.value.status_code == 404

    async def test_49_update_missing_404(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await update_supplier(
                sid=str(uuid4()), req=SupplierUpdate(name="x"),
                user=biz_a, db=db_tx,
            )
        assert exc.value.status_code == 404

    async def test_50_delete_missing_404(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await delete_supplier(sid=str(uuid4()), user=biz_a, db=db_tx)
        assert exc.value.status_code == 404


class _AuthHeaderRequest:
    headers = {"Authorization": "Bearer token-for-pytest"}


class _PoolAcquire:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, db):
        self.db = db

    def acquire(self):
        return _PoolAcquire(self.db)


class TestCertificateTenantBoundary:
    async def test_51_cross_tenant_user_cannot_view_supplier_certificate(
        self, db_tx, biz_a, biz_b, tmp_path, monkeypatch
    ):
        supplier_b = await _create(db_tx, biz_b, name="B certificate owner")
        cert_path = tmp_path / "tenant-b-cert.pdf"
        cert_path.write_bytes(b"%PDF-1.4\n%pytest tenant boundary\n")
        cert_id = uuid4()
        await db_tx.execute(
            """
            INSERT INTO supplier_certificates
                (id, supplier_id, tenant_id, cert_type, file_path, original_filename, file_size)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7)
            """,
            cert_id,
            supplier_b["id"],
            biz_b["tenant_id"],
            "halal_cert",
            str(cert_path),
            "tenant-b-cert.pdf",
            cert_path.stat().st_size,
        )

        import auth.db as auth_db
        import supply_chain.supplier_router as supplier_router

        monkeypatch.setattr(supplier_router, "decode_token", lambda _token: biz_a)
        monkeypatch.setattr(auth_db, "get_pool", lambda: _Pool(db_tx))

        with pytest.raises(HTTPException) as exc:
            await view_certificate(
                sid=supplier_b["id"],
                cid=str(cert_id),
                request=cast(Any, _AuthHeaderRequest()),
            )

        assert exc.value.status_code in (403, 404)
