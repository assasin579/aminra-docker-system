"""Full-coverage test suite for production batch CRUD lifecycle (50 cases).

Production batches sit at the centre of supply chain traceability:
- FK to process_templates (optional)
- M2M to materials via batch_materials
- 1:N batch_steps auto-generated from process flowchart
- batch_status enum: draft → in_progress → completed/rejected (terminal)
- batch_code unique-ish (auto-gen LOT-YYYYMMDD-XXXXXX)

Tests cover: happy path, FK constraints (cross-tenant, missing refs), batch_code
uniqueness assumption, status transitions + side-effects (started_at /
completed_at), step auto-creation from process flowchart, multi-tenant,
role gating, edge cases.
"""
from __future__ import annotations

from uuid import uuid4
from typing import Any, cast

import pytest
from fastapi import HTTPException

from supply_chain.models import (
    BatchCreate, BatchUpdate, MaterialCreate, ProcessCreate, SupplierCreate,
)
from supply_chain.batch_router import (
    create_batch,
    delete_batch,
    get_batch,
    list_batches,
    update_batch,
    upload_step_photo,
    view_step_photo,
)
from supply_chain.material_router import create_material
from supply_chain.process_router import create_process
from supply_chain.supplier_router import create_supplier


# ─── helpers ─────────────────────────────────────────────────────────────────


async def _new_supplier(db, user, name=None):
    r = await create_supplier(
        req=SupplierCreate(name=name or f"S {uuid4().hex[:6]}"),
        user=user, db=db,
    )
    return r["id"]


async def _new_material(db, user, supplier_id, name=None):
    r = await create_material(
        req=MaterialCreate(name=name or f"M {uuid4().hex[:6]}", supplier_id=supplier_id),
        user=user, db=db,
    )
    return r["id"]


async def _new_process(db, user, name=None, flowchart=None):
    r = await create_process(
        req=ProcessCreate(name=name or f"P {uuid4().hex[:6]}", flowchart=flowchart),
        user=user, db=db,
    )
    return r["id"]


async def _new_batch(db, user, **kw):
    payload = {
        "product_name": kw.pop("product_name", f"Prod {uuid4().hex[:6]}"),
        **kw,
    }
    return await create_batch(req=BatchCreate(**payload), user=user, db=db)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1: HAPPY PATH (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHappyPath:
    async def test_01_full_payload(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup)
        proc = await _new_process(db_tx, biz_a)
        r = await _new_batch(
            db_tx, biz_a,
            batch_code="LOT-20260508-ABCDEF",
            product_name="Bánh Halal lô 1",
            process_template_id=proc,
            notes="Lô đầu tháng 5",
            materials=[{"material_id": mat, "quantity": 100, "unit": "kg"}],
        )
        assert "id" in r and r["message"] == "Đã tạo lô hàng"

    async def test_02_minimal_only_product_name(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="MinProd")
        assert "id" in r

    async def test_03_auto_generated_batch_code_format(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="auto code")
        row = await db_tx.fetchrow("SELECT batch_code FROM production_batches WHERE id=$1", r["id"])
        # Format: LOT-YYYYMMDD-XXXXXX
        assert row["batch_code"].startswith("LOT-")
        parts = row["batch_code"].split("-")
        assert len(parts) == 3 and len(parts[1]) == 8 and len(parts[2]) == 6

    async def test_04_default_status_draft(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="status")
        row = await db_tx.fetchrow("SELECT status FROM production_batches WHERE id=$1", r["id"])
        assert row["status"] == "draft"

    async def test_05_with_process_no_materials(self, db_tx, biz_a):
        proc = await _new_process(db_tx, biz_a)
        r = await _new_batch(db_tx, biz_a, product_name="proc only", process_template_id=proc)
        assert "id" in r


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2: REQUIRED FIELDS (3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequiredFields:
    async def test_06_missing_product_name_pydantic_rejects(self, db_tx):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            BatchCreate()

    async def test_07_empty_product_name_rejected(self, db_tx, biz_a):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            await _new_batch(db_tx, biz_a, product_name="")

    async def test_08_invalid_process_template_uuid_400(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await _new_batch(
                db_tx, biz_a, product_name="bad proc",
                process_template_id="not-uuid",
            )
        assert exc.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3: FK CONSTRAINTS (7)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFKConstraints:
    async def test_09_process_template_does_not_exist(self, db_tx, biz_a):
        # FK violation when process_template_id doesn't exist
        with pytest.raises(Exception):
            await _new_batch(
                db_tx, biz_a, product_name="ghost proc",
                process_template_id=str(uuid4()),
            )

    async def test_10_process_template_other_tenant_blocked(self, db_tx, biz_a, biz_b):
        proc_b = await _new_process(db_tx, biz_b, name="B's proc")
        with pytest.raises(HTTPException) as exc:
            await _new_batch(
                db_tx, biz_a, product_name="cross tenant proc",
                process_template_id=proc_b,
            )
        assert exc.value.status_code == 400

    async def test_11_material_does_not_exist_fk_violation(self, db_tx, biz_a):
        with pytest.raises(Exception):
            await _new_batch(
                db_tx, biz_a, product_name="ghost mat",
                materials=[{"material_id": str(uuid4()), "quantity": 1, "unit": "kg"}],
            )

    async def test_12_material_invalid_uuid_400(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await _new_batch(
                db_tx, biz_a, product_name="bad mat uuid",
                materials=[{"material_id": "not-uuid", "quantity": 1}],
            )
        assert exc.value.status_code == 400

    async def test_13_material_from_other_tenant_blocked(self, db_tx, biz_a, biz_b):
        sup_b = await _new_supplier(db_tx, biz_b)
        mat_b = await _new_material(db_tx, biz_b, sup_b)
        with pytest.raises(HTTPException) as exc:
            await _new_batch(
                db_tx, biz_a, product_name="cross mat",
                materials=[{"material_id": mat_b, "quantity": 5}],
            )
        assert exc.value.status_code == 400

    async def test_14_multiple_materials_attached(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mats = [await _new_material(db_tx, biz_a, sup) for _ in range(3)]
        r = await _new_batch(
            db_tx, biz_a, product_name="multi mat",
            materials=[{"material_id": m, "quantity": i + 1, "unit": "kg"} for i, m in enumerate(mats)],
        )
        # Verify all 3 batch_materials rows created
        count = await db_tx.fetchval(
            "SELECT COUNT(*) FROM batch_materials WHERE batch_id=$1::uuid", r["id"]
        )
        assert count == 3

    async def test_15_no_materials_array_no_batch_materials_rows(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="no mat")
        count = await db_tx.fetchval(
            "SELECT COUNT(*) FROM batch_materials WHERE batch_id=$1::uuid", r["id"]
        )
        assert count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4: BATCH_CODE FORMAT + UNIQUENESS (6)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBatchCode:
    async def test_16_explicit_batch_code_used(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, batch_code="MY-CUSTOM-001", product_name="custom")
        row = await db_tx.fetchrow("SELECT batch_code FROM production_batches WHERE id=$1", r["id"])
        assert row["batch_code"] == "MY-CUSTOM-001"

    async def test_17_batch_code_max_100(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, batch_code="X" * 100, product_name="max code")
        assert "id" in r

    async def test_18_batch_code_over_100_rejected(self, db_tx, biz_a):
        with pytest.raises(Exception):
            await _new_batch(db_tx, biz_a, batch_code="X" * 101, product_name="over")

    async def test_19_duplicate_batch_code_rejected_within_tenant(self, db_tx, biz_a):
        # UNIQUE (tenant_id, batch_code) now enforced — second insert fails.
        await _new_batch(db_tx, biz_a, batch_code="DUP-001", product_name="A")
        with pytest.raises(Exception):  # asyncpg UniqueViolationError
            await _new_batch(db_tx, biz_a, batch_code="DUP-001", product_name="B")

    async def test_20_auto_code_unique_within_tenant(self, db_tx, biz_a):
        # Auto-generated codes use uuid4 suffix → collision is astronomically
        # unlikely. Sample 5 to show diversity.
        codes = set()
        for _ in range(5):
            r = await _new_batch(db_tx, biz_a, product_name="auto u")
            row = await db_tx.fetchrow("SELECT batch_code FROM production_batches WHERE id=$1", r["id"])
            codes.add(row["batch_code"])
        assert len(codes) == 5

    async def test_21_empty_batch_code_falls_back_to_auto(self, db_tx, biz_a):
        r = await create_batch(
            req=BatchCreate(batch_code=None, product_name="fallback"),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT batch_code FROM production_batches WHERE id=$1", r["id"])
        assert row["batch_code"].startswith("LOT-")


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5: LENGTH BOUNDARIES (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLengthBoundaries:
    async def test_22_product_name_at_255(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="P" * 255)
        assert "id" in r

    async def test_23_product_name_over_255_rejected(self, db_tx, biz_a):
        with pytest.raises(Exception):
            await _new_batch(db_tx, biz_a, product_name="P" * 256)

    async def test_24_notes_50000_chars(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="long n", notes="N" * 50000)
        assert "id" in r

    async def test_25_material_unit_at_50(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup)
        r = await _new_batch(
            db_tx, biz_a, product_name="unit max",
            materials=[{"material_id": mat, "quantity": 1, "unit": "u" * 50}],
        )
        assert "id" in r

    async def test_26_material_unit_over_50_rejected(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup)
        with pytest.raises(Exception):
            await _new_batch(
                db_tx, biz_a, product_name="unit over",
                materials=[{"material_id": mat, "quantity": 1, "unit": "u" * 51}],
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6: STATUS TRANSITIONS + SIDE EFFECTS (6)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusTransitions:
    async def test_27_draft_to_in_progress_sets_started_at(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="start")
        await update_batch(
            bid=r["id"], req=BatchUpdate(status="in_progress"),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow(
            "SELECT status, started_at FROM production_batches WHERE id=$1", r["id"]
        )
        assert row["status"] == "in_progress"
        assert row["started_at"] is not None

    async def test_28_in_progress_to_completed_sets_completed_at(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="finish")
        await update_batch(bid=r["id"], req=BatchUpdate(status="in_progress"), user=biz_a, db=db_tx)
        await update_batch(bid=r["id"], req=BatchUpdate(status="completed"), user=biz_a, db=db_tx)
        row = await db_tx.fetchrow(
            "SELECT status, completed_at FROM production_batches WHERE id=$1", r["id"]
        )
        assert row["status"] == "completed"
        assert row["completed_at"] is not None

    async def test_29_in_progress_to_rejected_sets_completed_at(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="reject")
        await update_batch(bid=r["id"], req=BatchUpdate(status="in_progress"), user=biz_a, db=db_tx)
        await update_batch(bid=r["id"], req=BatchUpdate(status="rejected"), user=biz_a, db=db_tx)
        row = await db_tx.fetchrow("SELECT completed_at FROM production_batches WHERE id=$1", r["id"])
        assert row["completed_at"] is not None

    async def test_30_invalid_status_rejected_by_db_enum(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="bad status")
        with pytest.raises(Exception):
            await update_batch(
                bid=r["id"], req=BatchUpdate(status="archived_xyz"),
                user=biz_a, db=db_tx,
            )

    async def test_31_skip_in_progress_draft_to_completed_blocked(self, db_tx, biz_a):
        # Transition matrix now enforces draft → in_progress before completed.
        r = await _new_batch(db_tx, biz_a, product_name="skip")
        with pytest.raises(HTTPException) as exc:
            await update_batch(bid=r["id"], req=BatchUpdate(status="completed"), user=biz_a, db=db_tx)
        assert exc.value.status_code == 409

    async def test_32_terminal_completed_cannot_be_mutated(self, db_tx, biz_a):
        # completed / rejected are terminal — any further status change → 409.
        r = await _new_batch(db_tx, biz_a, product_name="terminal")
        await update_batch(bid=r["id"], req=BatchUpdate(status="in_progress"), user=biz_a, db=db_tx)
        await update_batch(bid=r["id"], req=BatchUpdate(status="completed"), user=biz_a, db=db_tx)
        with pytest.raises(HTTPException) as exc:
            await update_batch(bid=r["id"], req=BatchUpdate(status="draft"), user=biz_a, db=db_tx)
        assert exc.value.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7: STEP AUTO-CREATION FROM PROCESS (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStepAutoCreation:
    async def test_33_steps_created_from_process_flowchart_nodes(self, db_tx, biz_a):
        proc = await _new_process(
            db_tx, biz_a,
            flowchart={
                "nodes": [
                    {"id": "n1", "label": "Tiếp nhận NL", "order": 1},
                    {"id": "n2", "label": "Pha trộn", "order": 2},
                    {"id": "n3", "label": "Đóng gói", "order": 3},
                ],
                "edges": [],
            },
        )
        r = await _new_batch(db_tx, biz_a, product_name="auto steps", process_template_id=proc)
        rows = await db_tx.fetch(
            "SELECT step_name FROM batch_steps WHERE batch_id=$1::uuid ORDER BY created_at",
            r["id"],
        )
        names = [row["step_name"] for row in rows]
        assert names == ["Tiếp nhận NL", "Pha trộn", "Đóng gói"]

    async def test_34_steps_respect_node_order(self, db_tx, biz_a):
        proc = await _new_process(
            db_tx, biz_a,
            flowchart={
                "nodes": [
                    {"id": "n1", "label": "Last", "order": 99},
                    {"id": "n2", "label": "First", "order": 1},
                ],
                "edges": [],
            },
        )
        r = await _new_batch(db_tx, biz_a, product_name="ordered", process_template_id=proc)
        rows = await db_tx.fetch(
            "SELECT step_name, node_id FROM batch_steps WHERE batch_id=$1::uuid ORDER BY created_at",
            r["id"],
        )
        # Insertion follows sorted order
        assert rows[0]["step_name"] == "First"
        assert rows[1]["step_name"] == "Last"

    async def test_35_no_process_template_no_steps_created(self, db_tx, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="no proc")
        count = await db_tx.fetchval(
            "SELECT COUNT(*) FROM batch_steps WHERE batch_id=$1::uuid", r["id"]
        )
        assert count == 0

    async def test_36_steps_carry_checklist_from_node(self, db_tx, biz_a):
        proc = await _new_process(
            db_tx, biz_a,
            flowchart={
                "nodes": [
                    {"id": "n1", "label": "step", "checklist": ["Check temp", "Check pH"]},
                ],
                "edges": [],
            },
        )
        r = await _new_batch(db_tx, biz_a, product_name="checklist", process_template_id=proc)
        row = await db_tx.fetchrow(
            "SELECT checklist FROM batch_steps WHERE batch_id=$1::uuid", r["id"]
        )
        import json
        cl = json.loads(row["checklist"]) if isinstance(row["checklist"], str) else row["checklist"]
        assert cl == [
            {"text": "Check temp", "checked": False},
            {"text": "Check pH", "checked": False},
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8: MULTI-TENANT ISOLATION (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiTenant:
    async def test_37_biz_b_does_not_see_biz_a_batches(self, db_tx, biz_a, biz_b):
        await _new_batch(db_tx, biz_a, product_name="A's secret batch")
        listing = await list_batches(
            status=None, product=None, period=None, user=biz_b, db=db_tx,
        )
        # listing returns dict with a 'batches' key (or similar)
        prod_names = [getattr(b, "product_name", None) for b in listing.get("batches", [])]
        assert "A's secret batch" not in prod_names

    async def test_38_biz_b_get_404(self, db_tx, biz_a, biz_b):
        r = await _new_batch(db_tx, biz_a, product_name="A only get")
        with pytest.raises(HTTPException) as exc:
            await get_batch(bid=r["id"], user=biz_b, db=db_tx)
        assert exc.value.status_code == 404

    async def test_39_biz_b_update_404(self, db_tx, biz_a, biz_b):
        # update_batch now checks UPDATE result count and raises 404 when 0.
        r = await _new_batch(db_tx, biz_a, product_name="A only upd")
        with pytest.raises(HTTPException) as exc:
            await update_batch(
                bid=r["id"], req=BatchUpdate(product_name="hacked"),
                user=biz_b, db=db_tx,
            )
        assert exc.value.status_code == 404
        # Row must remain unchanged.
        row = await db_tx.fetchrow("SELECT product_name FROM production_batches WHERE id=$1", r["id"])
        assert row["product_name"] == "A only upd"

    async def test_40_biz_b_delete_404(self, db_tx, biz_a, biz_b):
        r = await _new_batch(db_tx, biz_a, product_name="A only del")
        with pytest.raises(HTTPException) as exc:
            await delete_batch(bid=r["id"], user=biz_b, db=db_tx)
        assert exc.value.status_code == 404

    async def test_41_list_filtered_by_status_only_owned(self, db_tx, biz_a, biz_b):
        await _new_batch(db_tx, biz_a, product_name="A draft")
        await _new_batch(db_tx, biz_b, product_name="B draft")
        listing = await list_batches(
            status="draft", product=None, period=None, user=biz_a, db=db_tx,
        )
        names = [getattr(b, "product_name", None) for b in listing.get("batches", [])]
        assert "A draft" in names
        assert "B draft" not in names


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9: ROLE GATING (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoleGating:
    async def test_42_provider_cannot_create(self, db_tx, prov_user):
        with pytest.raises(HTTPException) as exc:
            await _new_batch(db_tx, prov_user, product_name="hostile")
        assert exc.value.status_code == 403

    async def test_43_provider_cannot_list(self, db_tx, prov_user):
        with pytest.raises(HTTPException) as exc:
            await list_batches(
                status=None, product=None, period=None, user=prov_user, db=db_tx,
            )
        assert exc.value.status_code == 403

    async def test_44_provider_cannot_update(self, db_tx, prov_user, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="upd target")
        with pytest.raises(HTTPException) as exc:
            await update_batch(
                bid=r["id"], req=BatchUpdate(status="completed"),
                user=prov_user, db=db_tx,
            )
        assert exc.value.status_code == 403

    async def test_45_provider_cannot_delete(self, db_tx, prov_user, biz_a):
        r = await _new_batch(db_tx, biz_a, product_name="del target")
        with pytest.raises(HTTPException) as exc:
            await delete_batch(bid=r["id"], user=prov_user, db=db_tx)
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Group 10: SPECIAL CHARS + EDGE CASES (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpecialAndEdge:
    async def test_46_vn_diacritics_in_product_name(self, db_tx, biz_a):
        name = "Bánh trung thu Halal — vị truyền thống"
        r = await _new_batch(db_tx, biz_a, product_name=name)
        row = await db_tx.fetchrow("SELECT product_name FROM production_batches WHERE id=$1", r["id"])
        assert row["product_name"] == name

    async def test_47_emoji_in_batch_code(self, db_tx, biz_a):
        # Probably acceptable in DB but odd in trace URLs. Document current.
        r = await _new_batch(db_tx, biz_a, batch_code="LOT-🌟-001", product_name="emoji code")
        assert "id" in r

    async def test_48_sql_injection_in_product_name_safe(self, db_tx, biz_a):
        name = "'; DROP TABLE production_batches;--"
        r = await _new_batch(db_tx, biz_a, product_name=name)
        row = await db_tx.fetchrow("SELECT product_name FROM production_batches WHERE id=$1", r["id"])
        assert row["product_name"] == name
        await db_tx.fetchval("SELECT COUNT(*) FROM production_batches")

    async def test_49_delete_cascades_to_batch_materials_and_steps(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup)
        proc = await _new_process(
            db_tx, biz_a,
            flowchart={"nodes": [{"id": "n1", "label": "step1"}], "edges": []},
        )
        r = await _new_batch(
            db_tx, biz_a, product_name="cascade",
            process_template_id=proc,
            materials=[{"material_id": mat, "quantity": 1, "unit": "kg"}],
        )
        await delete_batch(bid=r["id"], user=biz_a, db=db_tx)

        bm = await db_tx.fetchval(
            "SELECT COUNT(*) FROM batch_materials WHERE batch_id=$1::uuid", r["id"]
        )
        bs = await db_tx.fetchval(
            "SELECT COUNT(*) FROM batch_steps WHERE batch_id=$1::uuid", r["id"]
        )
        assert bm == 0  # CASCADE
        assert bs == 0  # presumably also CASCADE

    async def test_50_get_returns_full_batch_with_materials_and_steps(self, db_tx, biz_a):
        sup = await _new_supplier(db_tx, biz_a)
        mat = await _new_material(db_tx, biz_a, sup, name="mat for get")
        proc = await _new_process(
            db_tx, biz_a,
            flowchart={"nodes": [{"id": "n1", "label": "GetStep"}], "edges": []},
        )
        r = await _new_batch(
            db_tx, biz_a, product_name="full get",
            process_template_id=proc,
            materials=[{"material_id": mat, "quantity": 5, "unit": "kg"}],
        )
        result = await get_batch(bid=r["id"], user=biz_a, db=db_tx)
        # Result should be a dict-ish object containing batch info
        assert result is not None
        # Sanity: at least one identifying field surfaces
        as_str = str(result)
        assert "full get" in as_str or "GetStep" in as_str or r["id"] in as_str


class _BytesUpload:
    def __init__(self, content: bytes, filename: str = "evidence.png"):
        self._content = content
        self.filename = filename

    async def read(self) -> bytes:
        return self._content


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


class TestPhotoTenantBoundary:
    async def _batch_with_one_step(self, db_tx, user):
        proc = await _new_process(
            db_tx, user,
            flowchart={"nodes": [{"id": "n1", "label": "PhotoStep"}], "edges": []},
        )
        batch = await _new_batch(db_tx, user, product_name="photo boundary", process_template_id=proc)
        step_id = await db_tx.fetchval(
            "SELECT id FROM batch_steps WHERE batch_id=$1::uuid LIMIT 1", batch["id"]
        )
        return batch["id"], str(step_id)

    async def test_51_cross_tenant_user_cannot_upload_step_photo(self, db_tx, biz_a, biz_b):
        bid_b, step_b = await self._batch_with_one_step(db_tx, biz_b)

        with pytest.raises(HTTPException) as exc:
            await upload_step_photo(
                bid=bid_b,
                step_id=step_b,
                file=cast(Any, _BytesUpload(b"not-a-real-png-but-small")),
                user=biz_a,
                db=db_tx,
            )

        assert exc.value.status_code in (403, 404)
        photo_path = await db_tx.fetchval("SELECT photo_path FROM batch_steps WHERE id=$1::uuid", step_b)
        assert photo_path is None

    async def test_52_cross_tenant_user_cannot_view_step_photo(self, db_tx, biz_a, biz_b, tmp_path, monkeypatch):
        bid_b, step_b = await self._batch_with_one_step(db_tx, biz_b)
        photo = tmp_path / "tenant-b-evidence.png"
        # Minimal PNG header + bytes. FileResponse creation is enough for the old leak.
        photo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        await db_tx.execute("UPDATE batch_steps SET photo_path=$1 WHERE id=$2::uuid", str(photo), step_b)

        import auth.db as auth_db
        import auth.jwt_utils as jwt_utils

        monkeypatch.setattr(jwt_utils, "decode_token", lambda _token: biz_a)
        monkeypatch.setattr(auth_db, "get_pool", lambda: _Pool(db_tx))

        with pytest.raises(HTTPException) as exc:
            await view_step_photo(bid=bid_b, step_id=step_b, request=cast(Any, _AuthHeaderRequest()))

        assert exc.value.status_code in (403, 404)
