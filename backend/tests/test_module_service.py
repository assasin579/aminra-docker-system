from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from auth.module_service import (
    create_module_activation_request,
    get_current_tenant_modules,
    list_module_activation_requests,
    provision_tenant_modules_for_industry,
    review_module_activation_request,
    set_tenant_module_status,
)


class Row(dict):
    def __getattr__(self, item):
        return self[item]


async def test_get_current_tenant_modules_returns_business_model_and_ordered_modules():
    db = AsyncMock()
    db.fetchrow = AsyncMock(
        return_value=Row(
            industry_code="food_manufacturing",
            industry_name_vi="Sản xuất thực phẩm",
            industry_name_en="Food manufacturing",
        )
    )
    db.fetch = AsyncMock(
        return_value=[
            Row(
                code="certification_dossier",
                name_vi="Hồ sơ chứng nhận",
                name_en="Certification dossier",
                category="certification",
                status="enabled",
                required=True,
                default_enabled=True,
                display_order=10,
                config={},
                source="business_model_default",
                updated_at=None,
            ),
            Row(
                code="daily_operations",
                name_vi="Vận hành hằng ngày",
                name_en="Daily operations",
                category="operations",
                status="disabled",
                required=False,
                default_enabled=False,
                display_order=80,
                config={"mvp": True},
                source="business_model_default",
                updated_at=None,
            ),
        ]
    )

    payload = await get_current_tenant_modules(db, {"tenant_id": "tenant-1"})

    assert payload == {
        "business_model": {
            "code": "food_manufacturing",
            "name_vi": "Sản xuất thực phẩm",
            "name_en": "Food manufacturing",
        },
        "modules": [
            {
                "code": "certification_dossier",
                "name_vi": "Hồ sơ chứng nhận",
                "name_en": "Certification dossier",
                "category": "certification",
                "status": "enabled",
                "required": True,
                "default_enabled": True,
                "display_order": 10,
                "config": {},
                "source": "business_model_default",
                "updated_at": None,
                "access_state": "active",
                "access_label_vi": "Đang hoạt động",
                "cta_label_vi": "Mở module",
                "route_path": "/dossiers",
            },
            {
                "code": "daily_operations",
                "name_vi": "Vận hành hằng ngày",
                "name_en": "Daily operations",
                "category": "operations",
                "status": "disabled",
                "required": False,
                "default_enabled": False,
                "display_order": 80,
                "config": {"mvp": True},
                "source": "business_model_default",
                "updated_at": None,
                "access_state": "disabled",
                "access_label_vi": "Chưa kích hoạt",
                "cta_label_vi": "Yêu cầu kích hoạt",
                "route_path": None,
            },
        ],
    }
    assert db.fetchrow.await_count == 1
    assert db.fetch.await_count == 1
    sql, tenant_id = db.fetch.call_args.args
    assert "tenant_modules" in sql
    assert "business_model_modules" in sql
    assert tenant_id == "tenant-1"


async def test_get_current_tenant_modules_rejects_user_without_tenant():
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await get_current_tenant_modules(db, {"sub": "user-1"})

    assert exc.value.status_code == 403
    assert exc.value.detail == "TENANT_REQUIRED"
    db.fetchrow.assert_not_called()
    db.fetch.assert_not_called()


async def test_get_current_tenant_modules_falls_back_to_empty_shape_when_registry_not_provisioned():
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])

    payload = await get_current_tenant_modules(db, {"tenant_id": "tenant-1"})

    assert payload == {"business_model": None, "modules": []}


async def test_provision_tenant_modules_for_industry_is_idempotent_and_preserves_admin_overrides():
    tenant_id = uuid4()
    industry_schema_id = uuid4()
    db = AsyncMock()
    db.fetchval = AsyncMock(return_value=7)

    provisioned = await provision_tenant_modules_for_industry(db, tenant_id, industry_schema_id)

    assert provisioned == 7
    db.fetchval.assert_awaited_once()
    sql, actual_tenant_id, actual_schema_id = db.fetchval.call_args.args
    assert actual_tenant_id == tenant_id
    assert actual_schema_id == industry_schema_id
    assert "INSERT INTO tenant_modules" in sql
    assert "FROM business_model_modules bmm" in sql
    assert "ON CONFLICT (tenant_id, module_id) DO UPDATE" in sql
    assert "tenant_modules.source = 'admin_override'" in sql
    assert "tenant_modules.status" in sql
    assert "tenant_modules.config" in sql
    assert "enabled_at" in sql
    assert "disabled_at" in sql
    assert "CASE WHEN bmm.default_enabled THEN NOW() ELSE NULL END" in sql
    assert "WHEN EXCLUDED.status IN ('enabled', 'trial')" in sql
    assert "WHEN EXCLUDED.status IN ('disabled', 'locked')" in sql


async def test_provision_tenant_modules_for_industry_rejects_missing_tenant():
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await provision_tenant_modules_for_industry(db, None, uuid4())

    assert exc.value.status_code == 403
    assert exc.value.detail == "TENANT_REQUIRED"
    db.fetchval.assert_not_called()


async def test_set_tenant_module_status_rejects_enabling_when_required_dependency_missing():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=Row(module_id="public-trace-id", code="public_trace", required=False))
    db.fetch = AsyncMock(return_value=[Row(code="traceability")])

    with pytest.raises(HTTPException) as exc:
        await set_tenant_module_status(db, tenant_id, "public_trace", "enabled")

    assert exc.value.status_code == 409
    assert exc.value.detail == "MODULE_DEPENDENCY_MISSING:traceability"
    db.execute.assert_not_called()


async def test_set_tenant_module_status_rejects_disabling_when_required_dependents_enabled():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=Row(module_id="traceability-id", code="traceability", required=False))
    db.fetch = AsyncMock(side_effect=[[], [Row(code="public_trace")]])

    with pytest.raises(HTTPException) as exc:
        await set_tenant_module_status(db, tenant_id, "traceability", "disabled")

    assert exc.value.status_code == 409
    assert exc.value.detail == "MODULE_DEPENDENT_ENABLED:public_trace"
    db.execute.assert_not_called()


async def test_set_tenant_module_status_blocks_disabling_required_default_module():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=Row(module_id="cert-id", code="certification_dossier", required=True))
    db.fetch = AsyncMock(return_value=[])

    with pytest.raises(HTTPException) as exc:
        await set_tenant_module_status(db, tenant_id, "certification_dossier", "disabled")

    assert exc.value.status_code == 409
    assert exc.value.detail == "MODULE_REQUIRED:certification_dossier"
    db.execute.assert_not_called()


async def test_set_tenant_module_status_writes_admin_override_after_dependency_checks():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=Row(module_id="traceability-id", code="traceability", required=False))
    db.fetch = AsyncMock(side_effect=[[], []])
    db.execute = AsyncMock(return_value="UPDATE 1")

    payload = await set_tenant_module_status(
        db,
        tenant_id,
        "traceability",
        "trial",
        config={"max_batches": 10},
    )

    assert payload == {
        "tenant_id": tenant_id,
        "module_code": "traceability",
        "status": "trial",
        "source": "admin_override",
        "config": {"max_batches": 10},
    }
    db.execute.assert_awaited_once()
    sql = db.execute.call_args.args[0]
    assert "UPDATE tenant_modules" in sql
    assert "source = 'admin_override'" in sql


async def test_create_module_activation_request_is_idempotent_for_pending_disabled_module():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetchrow = AsyncMock(
        side_effect=[
            Row(module_id="process-id", code="process_digitization", status="disabled", name_vi="Số hóa quy trình"),
            None,
            Row(
                id="request-1",
                tenant_id=tenant_id,
                module_code="process_digitization",
                module_name_vi="Số hóa quy trình",
                status="pending",
                message="Cần bật để demo quy trình",
                route_path="/supply-chain/process",
                requester_email="owner@example.com",
                created_at=None,
                updated_at=None,
            ),
        ]
    )

    payload = await create_module_activation_request(
        db,
        {"tenant_id": tenant_id, "sub": "kc-sub", "email": "owner@example.com"},
        "process_digitization",
        route_path="/supply-chain/process",
        message="Cần bật để demo quy trình",
    )

    assert payload["status"] == "pending"
    assert payload["module_code"] == "process_digitization"
    assert payload["module_name_vi"] == "Số hóa quy trình"
    assert payload["requester_email"] == "owner@example.com"
    assert db.fetchrow.await_count == 3
    insert_sql = db.fetchrow.call_args_list[2].args[0]
    assert "INSERT INTO module_activation_requests" in insert_sql
    assert "requester_subject" in insert_sql


async def test_create_module_activation_request_reuses_existing_pending_request_without_duplicate_insert():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetchrow = AsyncMock(
        side_effect=[
            Row(module_id="process-id", code="process_digitization", status="disabled", name_vi="Số hóa quy trình"),
            Row(
                id="request-existing",
                tenant_id=tenant_id,
                module_code="process_digitization",
                module_name_vi="Số hóa quy trình",
                status="pending",
                message="old",
                route_path="/supply-chain/process",
                requester_email="owner@example.com",
                created_at=None,
                updated_at=None,
            ),
        ]
    )

    payload = await create_module_activation_request(
        db,
        {"tenant_id": tenant_id, "sub": "kc-sub", "email": "owner@example.com"},
        "process_digitization",
        route_path="/supply-chain/process",
    )

    assert payload["id"] == "request-existing"
    assert db.fetchrow.await_count == 2


async def test_create_module_activation_request_rejects_already_active_module():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=Row(module_id="supplier-id", code="supplier_management", status="enabled", name_vi="Quản lý NCC"))

    with pytest.raises(HTTPException) as exc:
        await create_module_activation_request(db, {"tenant_id": tenant_id}, "supplier_management")

    assert exc.value.status_code == 409
    assert exc.value.detail == "MODULE_ALREADY_ACTIVE:supplier_management"


async def test_list_module_activation_requests_returns_admin_review_queue():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetch = AsyncMock(
        return_value=[
            Row(
                id="request-1",
                tenant_id=tenant_id,
                module_code="process_digitization",
                module_name_vi="Số hóa quy trình",
                status="pending",
                message="please enable",
                route_path="/supply-chain/process",
                requester_email="owner@example.com",
                created_at=None,
                updated_at=None,
            )
        ]
    )

    payload = await list_module_activation_requests(db, tenant_id=tenant_id)

    assert payload["requests"][0]["module_code"] == "process_digitization"
    sql = db.fetch.call_args.args[0]
    assert "FROM module_activation_requests mar" in sql
    assert "WHERE mar.tenant_id = $1" in sql


async def test_review_module_activation_request_approve_sets_trial_and_marks_request_approved():
    tenant_id = str(uuid4())
    db = AsyncMock()
    db.fetchrow = AsyncMock(
        side_effect=[
            Row(id="request-1", tenant_id=tenant_id, module_code="process_digitization", status="pending"),
            Row(module_id="process-id", code="process_digitization", required=False),
            Row(
                id="request-1",
                tenant_id=tenant_id,
                module_code="process_digitization",
                module_name_vi="Số hóa quy trình",
                status="approved",
                message="please enable",
                route_path="/supply-chain/process",
                requester_email="owner@example.com",
                created_at=None,
                updated_at=None,
            ),
        ]
    )
    db.fetch = AsyncMock(side_effect=[[], []])
    db.execute = AsyncMock(return_value="UPDATE 1")

    payload = await review_module_activation_request(
        db,
        "request-1",
        action="approve",
        admin={"sub": "admin-sub"},
        admin_note="trial approved",
    )

    assert payload["status"] == "approved"
    assert db.execute.await_count == 2
    module_update_sql = db.execute.call_args_list[0].args[0]
    request_update_sql = db.execute.call_args_list[1].args[0]
    assert "UPDATE tenant_modules" in module_update_sql
    assert "UPDATE module_activation_requests" in request_update_sql


async def test_review_module_activation_request_reject_marks_request_without_module_update():
    db = AsyncMock()
    db.fetchrow = AsyncMock(
        side_effect=[
            Row(id="request-1", tenant_id="tenant-1", module_code="process_digitization", status="pending"),
            Row(
                id="request-1",
                tenant_id="tenant-1",
                module_code="process_digitization",
                module_name_vi="Số hóa quy trình",
                status="rejected",
                message="please enable",
                route_path="/supply-chain/process",
                requester_email="owner@example.com",
                created_at=None,
                updated_at=None,
            ),
        ]
    )
    db.execute = AsyncMock(return_value="UPDATE 1")

    payload = await review_module_activation_request(db, "request-1", action="reject", admin={"sub": "admin-sub"}, admin_note="not in plan")

    assert payload["status"] == "rejected"
    assert db.execute.await_count == 1
