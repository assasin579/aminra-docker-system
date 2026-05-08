"""Full-coverage test suite for the process template CRUD lifecycle (50 cases).

Process templates store reusable production flowcharts (jsonb) referenced by
production_batches. Tests cover: happy path, flowchart structure validation
(intentionally permissive — server stores whatever JSON), multi-tenant isolation,
role gating, lifecycle (is_active, version), and FK protection from batches.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from supply_chain.models import ProcessCreate, ProcessUpdate
from supply_chain.process_router import (
    create_process,
    delete_process,
    get_process,
    list_processes,
    update_process,
)


# ─── helpers ─────────────────────────────────────────────────────────────────


def _flow(nodes=None, edges=None):
    return {"nodes": nodes or [], "edges": edges or []}


async def _create(db, user, **kw):
    payload = {"name": kw.pop("name", f"Proc {uuid4().hex[:6]}"), **kw}
    return await create_process(req=ProcessCreate(**payload), user=user, db=db)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1: HAPPY PATH (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHappyPath:
    async def test_01_full_payload_with_flowchart(self, db_tx, biz_a):
        flow = _flow(
            nodes=[{"id": "n1", "label": "Tiếp nhận NL"}, {"id": "n2", "label": "Pha trộn"}],
            edges=[{"source": "n1", "target": "n2"}],
        )
        r = await _create(
            db_tx, biz_a, name="QT sản xuất bánh halal",
            description="Quy trình chuẩn JAKIM", flowchart=flow,
        )
        assert "id" in r and r["message"] == "Đã tạo quy trình"

    async def test_02_minimal_only_name(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="Min process")
        # Default flowchart {nodes:[], edges:[]} must be applied
        row = await db_tx.fetchrow("SELECT flowchart FROM process_templates WHERE id=$1", r["id"])
        import json
        fc = json.loads(row["flowchart"]) if isinstance(row["flowchart"], str) else row["flowchart"]
        assert fc == {"nodes": [], "edges": []}

    async def test_03_with_description_only(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="desc only", description="X")
        assert "id" in r

    async def test_04_default_is_active_true(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="active")
        row = await db_tx.fetchrow("SELECT is_active FROM process_templates WHERE id=$1", r["id"])
        assert row["is_active"] is True

    async def test_05_default_version_1(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="v1")
        row = await db_tx.fetchrow("SELECT version FROM process_templates WHERE id=$1", r["id"])
        assert row["version"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2: REQUIRED FIELDS (2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequiredFields:
    async def test_06_missing_name_pydantic_rejects(self, db_tx):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ProcessCreate()

    async def test_07_empty_string_name_currently_accepted(self, db_tx, biz_a):
        # Pydantic has no min_length on name. Document gap.
        r = await _create(db_tx, biz_a, name="")
        assert "id" in r


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3: FLOWCHART JSON STRUCTURE (8)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlowchart:
    async def test_08_flowchart_with_nested_metadata(self, db_tx, biz_a):
        flow = _flow(
            nodes=[{"id": "n1", "label": "step1", "meta": {"duration": 30, "unit": "min"}}],
        )
        r = await _create(db_tx, biz_a, name="nested", flowchart=flow)
        row = await db_tx.fetchrow("SELECT flowchart FROM process_templates WHERE id=$1", r["id"])
        import json
        fc = json.loads(row["flowchart"]) if isinstance(row["flowchart"], str) else row["flowchart"]
        assert fc["nodes"][0]["meta"]["duration"] == 30

    async def test_09_flowchart_omitted_defaults_to_empty(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="omit fc")
        row = await db_tx.fetchrow("SELECT flowchart FROM process_templates WHERE id=$1", r["id"])
        import json
        fc = json.loads(row["flowchart"]) if isinstance(row["flowchart"], str) else row["flowchart"]
        assert fc == {"nodes": [], "edges": []}

    async def test_10_flowchart_with_100_nodes(self, db_tx, biz_a):
        flow = _flow(nodes=[{"id": f"n{i}", "label": f"step {i}"} for i in range(100)])
        r = await _create(db_tx, biz_a, name="big flow", flowchart=flow)
        assert "id" in r

    async def test_11_flowchart_invalid_structure_currently_accepted(self, db_tx, biz_a):
        # Server stores raw — no schema validation on flowchart shape.
        # Future: should validate {nodes: [], edges: []} or accept {} only.
        flow = {"random": "weird structure", "no_nodes_or_edges_key": True}
        r = await _create(db_tx, biz_a, name="weird fc", flowchart=flow)
        assert "id" in r

    async def test_12_flowchart_with_vn_labels(self, db_tx, biz_a):
        flow = _flow(nodes=[{"id": "n1", "label": "Đóng gói — niêm phong"}])
        r = await _create(db_tx, biz_a, name="vn fc", flowchart=flow)
        row = await db_tx.fetchrow("SELECT flowchart FROM process_templates WHERE id=$1", r["id"])
        import json
        fc = json.loads(row["flowchart"]) if isinstance(row["flowchart"], str) else row["flowchart"]
        assert "Đóng gói" in fc["nodes"][0]["label"]

    async def test_13_flowchart_update_replaces_not_merges(self, db_tx, biz_a):
        r = await _create(
            db_tx, biz_a, name="repl",
            flowchart=_flow(nodes=[{"id": "n1"}, {"id": "n2"}]),
        )
        await update_process(
            pid=r["id"], req=ProcessUpdate(flowchart=_flow(nodes=[{"id": "x"}])),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT flowchart FROM process_templates WHERE id=$1", r["id"])
        import json
        fc = json.loads(row["flowchart"]) if isinstance(row["flowchart"], str) else row["flowchart"]
        assert len(fc["nodes"]) == 1
        assert fc["nodes"][0]["id"] == "x"

    async def test_14_flowchart_with_unicode_characters(self, db_tx, biz_a):
        flow = _flow(nodes=[{"id": "n1", "label": "🍞 Bánh mì 食べ物"}])
        r = await _create(db_tx, biz_a, name="unicode fc", flowchart=flow)
        assert "id" in r

    async def test_15_flowchart_None_in_create_uses_default(self, db_tx, biz_a):
        r = await create_process(
            req=ProcessCreate(name="explicit none", flowchart=None),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT flowchart FROM process_templates WHERE id=$1", r["id"])
        import json
        fc = json.loads(row["flowchart"]) if isinstance(row["flowchart"], str) else row["flowchart"]
        assert fc == {"nodes": [], "edges": []}


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4: LENGTH BOUNDARIES (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLengthBoundaries:
    async def test_16_name_exactly_255(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="x" * 255)
        assert "id" in r

    async def test_17_name_256_db_rejects(self, db_tx, biz_a):
        with pytest.raises(Exception):
            await _create(db_tx, biz_a, name="x" * 256)

    async def test_18_description_50000_chars(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="long d", description="d" * 50000)
        assert "id" in r

    async def test_19_flowchart_with_huge_payload(self, db_tx, biz_a):
        # JSONB has 1GB limit; 1MB is safely under
        flow = _flow(nodes=[{"id": f"n{i}", "label": "x" * 1000} for i in range(1000)])
        r = await _create(db_tx, biz_a, name="huge fc", flowchart=flow)
        assert "id" in r

    async def test_20_name_with_only_whitespace_max_len(self, db_tx, biz_a):
        # Edge: length OK but content meaningless. Currently accepted.
        r = await _create(db_tx, biz_a, name=" " * 255)
        assert "id" in r


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5: MULTI-TENANT ISOLATION (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiTenant:
    async def test_21_biz_b_does_not_see_biz_a_processes(self, db_tx, biz_a, biz_b):
        await _create(db_tx, biz_a, name="A's process secret")
        listing = await list_processes(user=biz_b, db=db_tx)
        names = [p.name for p in listing["processes"]]
        assert "A's process secret" not in names

    async def test_22_biz_b_get_404(self, db_tx, biz_a, biz_b):
        r = await _create(db_tx, biz_a, name="A's get target")
        with pytest.raises(HTTPException) as exc:
            await get_process(pid=r["id"], user=biz_b, db=db_tx)
        assert exc.value.status_code == 404

    async def test_23_biz_b_update_404(self, db_tx, biz_a, biz_b):
        r = await _create(db_tx, biz_a, name="A's upd target")
        with pytest.raises(HTTPException) as exc:
            await update_process(
                pid=r["id"], req=ProcessUpdate(name="hacked"),
                user=biz_b, db=db_tx,
            )
        assert exc.value.status_code == 404

    async def test_24_biz_b_delete_404(self, db_tx, biz_a, biz_b):
        r = await _create(db_tx, biz_a, name="A's del target")
        with pytest.raises(HTTPException) as exc:
            await delete_process(pid=r["id"], user=biz_b, db=db_tx)
        assert exc.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6: ROLE GATING (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoleGating:
    async def test_25_provider_cannot_create(self, db_tx, prov_user):
        with pytest.raises(HTTPException) as exc:
            await _create(db_tx, prov_user, name="hostile")
        assert exc.value.status_code == 403

    async def test_26_provider_cannot_list(self, db_tx, prov_user):
        with pytest.raises(HTTPException) as exc:
            await list_processes(user=prov_user, db=db_tx)
        assert exc.value.status_code == 403

    async def test_27_provider_cannot_update(self, db_tx, prov_user, biz_a):
        r = await _create(db_tx, biz_a, name="upd target")
        with pytest.raises(HTTPException) as exc:
            await update_process(
                pid=r["id"], req=ProcessUpdate(name="hacked"),
                user=prov_user, db=db_tx,
            )
        assert exc.value.status_code == 403

    async def test_28_provider_cannot_delete(self, db_tx, prov_user, biz_a):
        r = await _create(db_tx, biz_a, name="del target")
        with pytest.raises(HTTPException) as exc:
            await delete_process(pid=r["id"], user=prov_user, db=db_tx)
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7: SPECIAL CHARS (4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpecialChars:
    async def test_29_vn_diacritics(self, db_tx, biz_a):
        name = "QT đóng gói thịt bò halal — TCVN"
        r = await _create(db_tx, biz_a, name=name)
        row = await db_tx.fetchrow("SELECT name FROM process_templates WHERE id=$1", r["id"])
        assert row["name"] == name

    async def test_30_emoji_in_name(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="🏭 SX Halal ✨")
        assert "id" in r

    async def test_31_sql_injection_in_name_safe(self, db_tx, biz_a):
        name = "'; DROP TABLE process_templates;--"
        r = await _create(db_tx, biz_a, name=name)
        row = await db_tx.fetchrow("SELECT name FROM process_templates WHERE id=$1", r["id"])
        assert row["name"] == name
        await db_tx.fetchval("SELECT COUNT(*) FROM process_templates")

    async def test_32_arabic_in_description(self, db_tx, biz_a):
        desc = "حلال process - JAKIM compliant"
        r = await _create(db_tx, biz_a, name="ar", description=desc)
        row = await db_tx.fetchrow("SELECT description FROM process_templates WHERE id=$1", r["id"])
        assert row["description"] == desc


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8: EDGE CASES (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    async def test_33_two_processes_same_name_same_tenant_succeed(self, db_tx, biz_a):
        a = await _create(db_tx, biz_a, name="Same QT")
        b = await _create(db_tx, biz_a, name="Same QT")
        assert a["id"] != b["id"]

    async def test_34_description_null_vs_empty_distinct(self, db_tx, biz_a):
        a = await _create(db_tx, biz_a, name="null desc")
        row_a = await db_tx.fetchrow("SELECT description FROM process_templates WHERE id=$1", a["id"])
        assert row_a["description"] is None

        b = await _create(db_tx, biz_a, name="empty desc", description="")
        row_b = await db_tx.fetchrow("SELECT description FROM process_templates WHERE id=$1", b["id"])
        assert row_b["description"] == ""

    async def test_35_partial_update_only_name(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="orig", description="orig desc")
        await update_process(
            pid=r["id"], req=ProcessUpdate(name="renamed"),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow(
            "SELECT name, description FROM process_templates WHERE id=$1", r["id"]
        )
        assert row["name"] == "renamed"
        assert row["description"] == "orig desc"  # unchanged

    async def test_36_empty_update_returns_no_change(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="noop")
        result = await update_process(
            pid=r["id"], req=ProcessUpdate(),
            user=biz_a, db=db_tx,
        )
        assert "Không có thay đổi" in result.get("message", "")

    async def test_37_get_returns_full_process_with_flowchart(self, db_tx, biz_a):
        r = await _create(
            db_tx, biz_a, name="full get",
            flowchart=_flow(nodes=[{"id": "n1"}]),
        )
        result = await get_process(pid=r["id"], user=biz_a, db=db_tx)
        # ProcessOut model serializes flowchart back as dict
        assert result.flowchart["nodes"][0]["id"] == "n1"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 9: BUSINESS LOGIC — is_active lifecycle (8)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsActiveLifecycle:
    async def test_38_deactivate_via_update(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="deact")
        await update_process(
            pid=r["id"], req=ProcessUpdate(is_active=False),
            user=biz_a, db=db_tx,
        )
        row = await db_tx.fetchrow("SELECT is_active FROM process_templates WHERE id=$1", r["id"])
        assert row["is_active"] is False

    async def test_39_reactivate(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="react")
        await update_process(pid=r["id"], req=ProcessUpdate(is_active=False), user=biz_a, db=db_tx)
        await update_process(pid=r["id"], req=ProcessUpdate(is_active=True), user=biz_a, db=db_tx)
        row = await db_tx.fetchrow("SELECT is_active FROM process_templates WHERE id=$1", r["id"])
        assert row["is_active"] is True

    async def test_40_inactive_processes_still_appear_in_list(self, db_tx, biz_a):
        # Listing currently does not filter by is_active. Document behavior;
        # PM may want a separate "active only" filter later.
        r = await _create(db_tx, biz_a, name="hidden?")
        await update_process(pid=r["id"], req=ProcessUpdate(is_active=False), user=biz_a, db=db_tx)
        listing = await list_processes(user=biz_a, db=db_tx)
        ids = [p.id for p in listing["processes"]]
        assert r["id"] in ids

    async def test_41_deactivated_can_be_referenced_by_existing_batch(self, db_tx, biz_a):
        # Once a batch references the process, deactivating shouldn't break
        # the batch.
        r = await _create(db_tx, biz_a, name="ref by batch")
        batch_id = uuid4()
        await db_tx.execute(
            "INSERT INTO production_batches (id, tenant_id, batch_code, product_name, process_template_id) "
            "VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)",
            batch_id, biz_a["tenant_id"], f"B-{uuid4().hex[:6]}", "p", r["id"],
        )
        await update_process(pid=r["id"], req=ProcessUpdate(is_active=False), user=biz_a, db=db_tx)
        # Batch still queryable
        b = await db_tx.fetchrow("SELECT process_template_id FROM production_batches WHERE id=$1", batch_id)
        assert str(b["process_template_id"]) == r["id"]

    async def test_42_delete_deactivated_succeeds_if_no_batch_ref(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="deact del")
        await update_process(pid=r["id"], req=ProcessUpdate(is_active=False), user=biz_a, db=db_tx)
        await delete_process(pid=r["id"], user=biz_a, db=db_tx)
        gone = await db_tx.fetchrow("SELECT id FROM process_templates WHERE id=$1", r["id"])
        assert gone is None

    async def test_43_delete_active_succeeds_if_no_batch_ref(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="active del")
        await delete_process(pid=r["id"], user=biz_a, db=db_tx)
        gone = await db_tx.fetchrow("SELECT id FROM process_templates WHERE id=$1", r["id"])
        assert gone is None

    async def test_44_delete_with_batch_reference_blocked_by_fk(self, db_tx, biz_a):
        r = await _create(db_tx, biz_a, name="ref blocked")
        await db_tx.execute(
            "INSERT INTO production_batches (id, tenant_id, batch_code, product_name, process_template_id) "
            "VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)",
            uuid4(), biz_a["tenant_id"], f"B-{uuid4().hex[:6]}", "p", r["id"],
        )
        with pytest.raises(Exception):
            await delete_process(pid=r["id"], user=biz_a, db=db_tx)

    async def test_45_update_with_only_is_active_no_other_field_works(self, db_tx, biz_a):
        # Defends against the bug where update requires at least 1 non-bool field.
        r = await _create(db_tx, biz_a, name="only flag")
        result = await update_process(
            pid=r["id"], req=ProcessUpdate(is_active=False),
            user=biz_a, db=db_tx,
        )
        assert "Đã cập nhật" in result.get("message", "") or "id" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Group 10: 404 + LISTING (5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotFoundAndList:
    async def test_46_get_missing_404(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await get_process(pid=str(uuid4()), user=biz_a, db=db_tx)
        assert exc.value.status_code == 404

    async def test_47_get_invalid_uuid_400(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await get_process(pid="not-uuid", user=biz_a, db=db_tx)
        assert exc.value.status_code == 400

    async def test_48_update_missing_404(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await update_process(
                pid=str(uuid4()), req=ProcessUpdate(name="x"),
                user=biz_a, db=db_tx,
            )
        assert exc.value.status_code == 404

    async def test_49_delete_missing_404(self, db_tx, biz_a):
        with pytest.raises(HTTPException) as exc:
            await delete_process(pid=str(uuid4()), user=biz_a, db=db_tx)
        assert exc.value.status_code == 404

    async def test_50_listing_returns_all_owned_processes(self, db_tx, biz_a):
        # NOTE: list endpoint sorts by updated_at DESC, but the BEFORE UPDATE
        # trigger overwrites any explicit updated_at we'd set, so a strict
        # ordering assertion is brittle in tests. Instead just assert both
        # rows surface in the listing — coverage of the multi-row read path.
        a = await _create(db_tx, biz_a, name="proc_a")
        b = await _create(db_tx, biz_a, name="proc_b")
        listing = await list_processes(user=biz_a, db=db_tx)
        ids = {p.id for p in listing["processes"]}
        assert {a["id"], b["id"]}.issubset(ids)
