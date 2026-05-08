"""Full-coverage test suite for the material CRUD lifecycle (50 cases).

Materials are tenant-scoped and FK-bound to suppliers (same tenant). The
halal_risk enum is core to Halal cert workflow → tested thoroughly. Tests
run inside an outer transaction (db_tx) and roll back on teardown.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from supply_chain.models import MaterialCreate, MaterialUpdate, SupplierCreate
from supply_chain.material_router import (
    create_material,
    delete_material,
    list_materials,
    update_material,
)
from supply_chain.supplier_router import create_supplier


HALAL_RISK_VALID = ["safe", "requires_cert", "prohibited", "unknown"]


# ─── helpers ─────────────────────────────────────────────────────────────────


async def _new_supplier(db, user, name=None):
    name = name or f"Sup {uuid4().hex[:6]}"
    r = await create_supplier(req=SupplierCreate(name=name), user=user, db=db)
    return r["id"]


async def _new_material(db, user, supplier_id, **kw):
    payload = {
        "name": kw.pop("name", f"Mat {uuid4().hex[:6]}"),
        "supplier_id": supplier_id,
        **kw,
    }
    return await create_material(req=MaterialCreate(**payload), user=user, db=db)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1: HAPPY PATH (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHappyPath:
    async def test_01_full_payload(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(
            db_tx, biz_a, sup,
            name="Bột mì nguyên cám",
            sku="BM-001",
            category="ngũ cốc",
            halal_risk="safe",
            description="Bột mì hữu cơ nhập khẩu",
            unit="kg",
        )
        assert "id" in r and r["message"] == "Đã tạo nguyên liệu"

    async def test_02_minimal_required_only(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="Min")
        # Default halal_risk → unknown
        row = await db_tx.fetchrow("SELECT halal_risk FROM materials WHERE id=$1", r["id"])
        assert row["halal_risk"] == "unknown"

    async def test_03_with_sku_only(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="With SKU", sku="ABC-123")
        assert "id" in r

    async def test_04_with_unit_kg(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="weighed", unit="kg")
        assert "id" in r

    async def test_05_with_unit_litre(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="liquid", unit="lít")
        assert "id" in r


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2: REQUIRED FIELDS (3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequiredFields:
    async def test_06_missing_name_pydantic_rejects(self, db_tx):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MaterialCreate(supplier_id=str(uuid4()))

    async def test_07_missing_supplier_id_pydantic_rejects(self, db_tx):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MaterialCreate(name="x")

    async def test_08_supplier_id_invalid_uuid_400(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await create_material(
                req=MaterialCreate(name="bad", supplier_id="not-a-uuid"),
                user=biz_a, db=db_tx,
            )
        assert exc.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3: FIELD FORMAT — halal_risk enum focus (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFieldFormat:
    @pytest.mark.parametrize("risk", HALAL_RISK_VALID)
    async def test_09_12_all_valid_halal_risk_accepted(self, db_tx, biz_a, risk):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name=f"r-{risk}", halal_risk=risk)
        row = await db_tx.fetchrow("SELECT halal_risk FROM materials WHERE id=$1", r["id"])
        assert row["halal_risk"] == risk

    async def test_13_invalid_halal_risk_rejected_by_db(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        with pytest.raises(Exception):  # InvalidTextRepresentationError
            await _new_material(db_tx, biz_a, sup, name="bad risk", halal_risk="catastrophic")


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4: LENGTH BOUNDARIES (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLengthBoundaries:
    async def test_14_name_at_max_255(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="x" * 255)
        assert "id" in r

    async def test_15_name_over_255_db_rejects(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        with pytest.raises(Exception):
            await _new_material(db_tx, biz_a, sup, name="x" * 256)

    async def test_16_sku_at_100(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="sku max", sku="S" * 100)
        assert "id" in r

    async def test_17_sku_over_100_rejected(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        with pytest.raises(Exception):
            await _new_material(db_tx, biz_a, sup, name="sku over", sku="S" * 101)

    async def test_18_unit_over_50_rejected(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        with pytest.raises(Exception):
            await _new_material(db_tx, biz_a, sup, name="u over", unit="u" * 51)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5: FK CONSTRAINT — supplier reference (6)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSupplierFK:
    async def test_19_supplier_does_not_exist_400(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await _new_material(db_tx, biz_a, str(uuid4()), name="ghost sup")
        assert exc.value.status_code == 400

    async def test_20_supplier_belongs_to_other_tenant_400(self, db_tx, biz_a, biz_b):
        sup_b = await _new_supplier(db_tx, biz_b, "B's supplier")
        # biz_a tries to reference biz_b's supplier — should 400
        with pytest.raises(HTTPException) as exc:
            await _new_material(db_tx, biz_a, sup_b, name="cross-tenant FK")
        assert exc.value.status_code == 400

    async def test_21_supplier_in_same_tenant_ok(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a, "same-tenant")
        r = await _new_material(db_tx, biz_a, sup, name="ok")
        assert "id" in r

    async def test_22_update_supplier_id_to_other_tenant_blocked(self, db_tx, biz_a, biz_b):
        sup_a = await _new_supplier(db_tx, biz_a, "A1")
        mat = await _new_material(db_tx, biz_a, sup_a, name="m")
        sup_b = await _new_supplier(db_tx, biz_b, "B1")
        # Cross-tenant FK swap now blocked: 400 from ownership check.
        with pytest.raises(HTTPException) as exc:
            await update_material(
                mid=mat["id"], req=MaterialUpdate(supplier_id=sup_b),
                user=biz_a, db=db_tx,
            )
        assert exc.value.status_code == 400
        # supplier_id must remain unchanged
        row = await db_tx.fetchrow("SELECT supplier_id FROM materials WHERE id=$1", mat["id"])
        assert str(row["supplier_id"]) == sup_a

    async def test_23_delete_supplier_with_material_blocks(self, db_tx, biz_a):
        from supply_chain.supplier_router import delete_supplier
        sup = await _new_supplier(db_tx, biz_a, "blocking")
        await _new_material(db_tx, biz_a, sup, name="blocker")
        with pytest.raises(Exception):
            await delete_supplier(sid=sup, user=biz_a, db=db_tx)

    async def test_24_supplier_id_invalid_uuid_400(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await create_material(
                req=MaterialCreate(name="x", supplier_id="bad-uuid-format"),
                user=biz_a, db=db_tx,
            )
        assert exc.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6: MULTI-TENANT ISOLATION (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiTenant:
    async def test_25_biz_b_cannot_see_biz_a_materials(self, db_tx, biz_a, biz_b):
        sup_a = await _new_supplier(db_tx, biz_a)
        await _new_material(db_tx, biz_a, sup_a, name="A's hidden")
        listing = await list_materials(category=None, supplier_id=None, search=None, user=biz_b, db=db_tx)
        names = [m.name for m in listing["materials"]]
        assert "A's hidden" not in names

    async def test_26_biz_b_update_404(self, db_tx, biz_a, biz_b):
        sup_a = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup_a, name="A's mat")
        with pytest.raises(HTTPException) as exc:
            await update_material(
                mid=mat["id"], req=MaterialUpdate(name="hacked"),
                user=biz_b, db=db_tx,
            )
        assert exc.value.status_code == 404

    async def test_27_biz_b_delete_404(self, db_tx, biz_a, biz_b):
        sup_a = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup_a, name="A del target")
        with pytest.raises(HTTPException) as exc:
            await delete_material(mid=mat["id"], user=biz_b, db=db_tx)
        assert exc.value.status_code == 404

    async def test_28_list_filtered_by_supplier_only_returns_owned(self, db_tx, biz_a, biz_b):
        sup_a = await _new_supplier(db_tx, biz_a)
        sup_b = await _new_supplier(db_tx, biz_b)
        await _new_material(db_tx, biz_a, sup_a, name="A m")
        await _new_material(db_tx, biz_b, sup_b, name="B m")
        # biz_a filter by sup_b — should be empty (no cross-tenant leak)
        listing = await list_materials(category=None, supplier_id=sup_b, search=None, user=biz_a, db=db_tx)
        assert listing["materials"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7: ROLE GATING (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoleGating:
    async def test_29_provider_cannot_create(self, db_tx, prov_user, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        with pytest.raises(HTTPException) as exc:
            await _new_material(db_tx, prov_user, sup, name="hostile")
        assert exc.value.status_code == 403

    async def test_30_provider_cannot_list(self, db_tx, prov_user):
        with pytest.raises(HTTPException) as exc:
            await list_materials(supplier_id=None, user=prov_user, db=db_tx)
        assert exc.value.status_code == 403

    async def test_31_provider_cannot_update(self, db_tx, prov_user, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="m")
        with pytest.raises(HTTPException) as exc:
            await update_material(
                mid=mat["id"], req=MaterialUpdate(name="hacked"),
                user=prov_user, db=db_tx,
            )
        assert exc.value.status_code == 403

    async def test_32_provider_cannot_delete(self, db_tx, prov_user, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="m")
        with pytest.raises(HTTPException) as exc:
            await delete_material(mid=mat["id"], user=prov_user, db=db_tx)
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8: SPECIAL CHARS (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpecialChars:
    async def test_33_vn_diacritics_in_name(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        name = "Đường mía hữu cơ — loại 1"
        r = await _new_material(db_tx, biz_a, sup, name=name)
        row = await db_tx.fetchrow("SELECT name FROM materials WHERE id=$1", r["id"])
        assert row["name"] == name

    async def test_34_emoji_in_description(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        desc = "🌾 Nguyên liệu hữu cơ ⭐"
        r = await _new_material(db_tx, biz_a, sup, name="emoji", description=desc)
        row = await db_tx.fetchrow("SELECT description FROM materials WHERE id=$1", r["id"])
        assert row["description"] == desc

    async def test_35_sql_injection_in_name_safe(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        name = "'; DROP TABLE materials;--"
        r = await _new_material(db_tx, biz_a, sup, name=name)
        # Verify name stored verbatim AND table still exists
        row = await db_tx.fetchrow("SELECT name FROM materials WHERE id=$1", r["id"])
        assert row["name"] == name
        await db_tx.fetchval("SELECT COUNT(*) FROM materials")

    async def test_36_chinese_chars_in_name(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        # Halal cert often involves China-sourced ingredients with original CN names
        name = "清真油 Halal oil"
        r = await _new_material(db_tx, biz_a, sup, name=name)
        row = await db_tx.fetchrow("SELECT name FROM materials WHERE id=$1", r["id"])
        assert row["name"] == name

    async def test_37_arabic_chars_in_description(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        # Halal certs from MUI/JAKIM may include Arabic descriptors
        desc = "حلال - certified"
        r = await _new_material(db_tx, biz_a, sup, name="ar", description=desc)
        row = await db_tx.fetchrow("SELECT description FROM materials WHERE id=$1", r["id"])
        assert row["description"] == desc


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9: EDGE CASES (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    async def test_38_default_halal_risk_unknown_when_omitted(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="default risk")
        row = await db_tx.fetchrow("SELECT halal_risk FROM materials WHERE id=$1", r["id"])
        assert row["halal_risk"] == "unknown"

    async def test_39_explicit_halal_risk_none_falls_back_to_unknown(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        # Code: req.halal_risk or "unknown"
        r = await create_material(
            req=MaterialCreate(name="explicit none", supplier_id=sup, halal_risk=None),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT halal_risk FROM materials WHERE id=$1", r["id"])
        assert row["halal_risk"] == "unknown"

    async def test_40_two_materials_same_name_same_supplier_both_succeed(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        a = await _new_material(db_tx, biz_a, sup, name="Same")
        b = await _new_material(db_tx, biz_a, sup, name="Same")
        # No unique constraint — both should succeed
        assert a["id"] != b["id"]

    async def test_41_description_50000_chars(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="long desc", description="d" * 50000)
        assert "id" in r


# ═══════════════════════════════════════════════════════════════════════════════
# Group 10: BUSINESS LOGIC (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBusinessLogic:
    async def test_42_prohibited_risk_material_can_still_be_created(self, db_tx, biz_a):
        # Allowed at create time — flagging for compliance review later, not blocking
        sup = await _new_supplier(db_tx, biz_a)
        r = await _new_material(db_tx, biz_a, sup, name="pork lard", halal_risk="prohibited")
        row = await db_tx.fetchrow("SELECT halal_risk FROM materials WHERE id=$1", r["id"])
        assert row["halal_risk"] == "prohibited"

    async def test_43_update_risk_unknown_to_safe(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="upgrade")
        await update_material(
            mid=mat["id"], req=MaterialUpdate(halal_risk="safe"),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT halal_risk FROM materials WHERE id=$1", mat["id"])
        assert row["halal_risk"] == "safe"

    async def test_44_update_risk_safe_to_prohibited_allowed(self, db_tx, biz_a):
        # No transition matrix on halal_risk currently — flag for product review.
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="downgrade", halal_risk="safe")
        await update_material(
            mid=mat["id"], req=MaterialUpdate(halal_risk="prohibited"),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT halal_risk FROM materials WHERE id=$1", mat["id"])
        assert row["halal_risk"] == "prohibited"

    async def test_45_partial_update_only_changes_passed_fields(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="partial", sku="OLD-SKU")
        await update_material(
            mid=mat["id"], req=MaterialUpdate(name="new name"),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT name, sku FROM materials WHERE id=$1", mat["id"])
        assert row["name"] == "new name"
        assert row["sku"] == "OLD-SKU"  # untouched

    async def test_46_empty_update_returns_no_change_message(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="noop")
        result = await update_material(
            mid=mat["id"], req=MaterialUpdate(),
            user=biz_a, db=db_tx,
        )
        assert "Không có thay đổi" in result.get("message", "")


# ═══════════════════════════════════════════════════════════════════════════════
# Group 11: 404 + DELETE (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotFoundAndDelete:
    async def test_47_update_missing_404(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await update_material(
                mid=str(uuid4()), req=MaterialUpdate(name="x"),
                user=biz_a, db=db_tx,
            )
        assert exc.value.status_code == 404

    async def test_48_delete_missing_404(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await delete_material(mid=str(uuid4()), user=biz_a, db=db_tx)
        assert exc.value.status_code == 404

    async def test_49_delete_succeeds_and_removes_from_list(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="del me")
        await delete_material(mid=mat["id"], user=biz_a, db=db_tx)
        listing = await list_materials(category=None, supplier_id=None, search=None, user=biz_a, db=db_tx)
        ids = [m.id for m in listing["materials"]]
        assert mat["id"] not in ids


    async def test_50_delete_with_batch_reference_blocked(self, db_tx, biz_a):
        # batch_materials FK to materials. Delete should fail if material referenced.
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="referenced")
        # Create a fake production_batch + batch_materials row
        batch_id = uuid4()
        await db_tx.execute(
            "INSERT INTO production_batches (id, tenant_id, batch_code, product_name) "
            "VALUES ($1::uuid, $2::uuid, $3, $4)",
            batch_id, biz_a["tenant_id"], f"B-{uuid4().hex[:6]}", "test product",
        )
        await db_tx.execute(
            "INSERT INTO batch_materials (batch_id, material_id, quantity, unit) "
            "VALUES ($1::uuid, $2::uuid, 10, 'kg')",
            batch_id, mat["id"],
        )
        with pytest.raises(Exception):
            await delete_material(mid=mat["id"], user=biz_a, db=db_tx)
