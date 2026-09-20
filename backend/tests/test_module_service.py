from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from auth.module_service import (
    get_current_tenant_modules,
    provision_tenant_modules_for_industry,
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
