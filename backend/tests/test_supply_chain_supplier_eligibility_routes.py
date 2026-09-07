from __future__ import annotations

from datetime import date, timedelta
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from supply_chain.models import CertificateRiskAlertUpdate, SupplierCertificateEligibilityUpsert, SupplierCreate, SupplierUpdate
from supply_chain.supplier_router import (
    create_supplier,
    list_certificate_risk_alerts,
    list_eligible_suppliers_route,
    update_certificate_risk_alert,
    update_supplier,
    upsert_supplier_eligibility,
)

_MIGRATION_PATHS = [
    Path(__file__).resolve().parents[1] / "alembic/versions/038_cb_supplier_certificate_eligibility.py",
    Path(__file__).resolve().parents[1] / "alembic/versions/039_supplier_authority_batch_snapshot.py",
]


def _load_migration(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


MIGRATIONS = [_load_migration(path) for path in _MIGRATION_PATHS]


@pytest.fixture(autouse=True)
async def _p0a_schema(db_tx):
    """Create P0-A schema inside each transactional route test."""
    await db_tx.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    for migration in reversed(MIGRATIONS):
        for sql in migration.DOWN_SQL:
            await db_tx.execute(sql)
    for migration in MIGRATIONS:
        for sql in migration.UP_SQL:
            await db_tx.execute(sql)


async def _supplier(db, user, name="Route Supplier"):
    r = await create_supplier(SupplierCreate(name=f"{name} {uuid4().hex[:6]}"), user=user, db=db)
    return r["id"]


async def _source_cert(db, tenant_id, provider, *, status="active", expiry_days=365):
    submission = await db.fetchrow(
        """
        INSERT INTO submissions (business_tenant, provider_id, document_ids, status, company_name)
        VALUES ($1,$2,'{}','approved','Supplier Tenant') RETURNING id
        """,
        tenant_id,
        provider["sub"],
    )
    cert = await db.fetchrow(
        """
        INSERT INTO halal_certificates
          (submission_id, cert_number, issued_by, business_tenant, company_name, expiry_date, status)
        VALUES ($1,$2,$3,$4,'Supplier Tenant',CURRENT_DATE + $5::int,$6) RETURNING id
        """,
        submission["id"],
        f"HC-{uuid4().hex[:8]}",
        provider["sub"],
        tenant_id,
        expiry_days,
        status,
    )
    return str(cert["id"])


def _req(*, status="active", source="cb", scope=None, vf=None, vu=None):
    today = date.today()
    return SupplierCertificateEligibilityUpsert(
        certificate_no=f"CB-{uuid4().hex[:8]}",
        issuer_name="Route CB",
        status=status,
        valid_from=vf or today - timedelta(days=1),
        valid_until=vu or today + timedelta(days=30),
        scope=scope if scope is not None else {},
        source_of_truth=source,
        reason="test",
    )


async def test_eligible_supplier_appears_and_ineligible_statuses_hidden(db_tx, biz_a, prov_user):
    good = await _supplier(db_tx, biz_a, "Good")
    expired = await _supplier(db_tx, biz_a, "Expired")
    suspended = await _supplier(db_tx, biz_a, "Suspended")
    revoked = await _supplier(db_tx, biz_a, "Revoked")
    await _source_cert(db_tx, biz_a["tenant_id"], prov_user)
    await upsert_supplier_eligibility(good, _req(), user=prov_user, db=db_tx)
    await upsert_supplier_eligibility(expired, _req(status="expired"), user=prov_user, db=db_tx)
    await upsert_supplier_eligibility(suspended, _req(status="suspended"), user=prov_user, db=db_tx)
    await upsert_supplier_eligibility(revoked, _req(status="revoked"), user=prov_user, db=db_tx)

    result = await list_eligible_suppliers_route(material_category=None, user=biz_a, db=db_tx)

    ids = [s.id for s in result["suppliers"]]
    assert good in ids
    assert expired not in ids
    assert suspended not in ids
    assert revoked not in ids


async def test_uploaded_supplier_certificate_without_cb_eligibility_hidden(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)
    await db_tx.execute(
        """
        INSERT INTO supplier_certificates
          (supplier_id, tenant_id, cert_type, cert_number, issuing_body, issued_date, expiry_date)
        VALUES ($1,$2,'halal_cert','SUP-UPLOAD','Self',CURRENT_DATE,CURRENT_DATE + 30)
        """,
        sid,
        biz_a["tenant_id"],
    )

    result = await list_eligible_suppliers_route(material_category=None, user=biz_a, db=db_tx)

    assert sid not in [s.id for s in result["suppliers"]]


async def test_cross_tenant_supplier_hidden(db_tx, biz_a, biz_b, prov_user):
    sid = await _supplier(db_tx, biz_a)
    await _source_cert(db_tx, biz_a["tenant_id"], prov_user)
    await upsert_supplier_eligibility(sid, _req(), user=prov_user, db=db_tx)

    result = await list_eligible_suppliers_route(material_category=None, user=biz_b, db=db_tx)

    assert sid not in [s.id for s in result["suppliers"]]


async def test_provider_can_create_and_update_certificate_status(db_tx, biz_a, prov_user):
    sid = await _supplier(db_tx, biz_a)
    source_cert_id = await _source_cert(db_tx, biz_a["tenant_id"], prov_user)

    created = await upsert_supplier_eligibility(sid, _req(status="active"), user=prov_user, db=db_tx)
    updated = await upsert_supplier_eligibility(sid, _req(status="suspended"), user=prov_user, db=db_tx)

    assert created["status"] == "active"
    assert created["source_certificate_id"] == source_cert_id
    assert created["id"] == updated["id"]
    assert updated["status"] == "suspended"


async def test_business_cannot_create_or_update_certificate_status(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)

    with pytest.raises(HTTPException) as exc:
        await upsert_supplier_eligibility(sid, _req(), user=biz_a, db=db_tx)

    assert exc.value.status_code == 403


async def test_revoke_fanout_alerts_only_active_related_buyers(db_tx, biz_a, biz_b, prov_user):
    sid = await _supplier(db_tx, biz_a)
    await _source_cert(db_tx, biz_a["tenant_id"], prov_user)
    cert = await upsert_supplier_eligibility(sid, _req(status="active"), user=prov_user, db=db_tx)
    unrelated = str(uuid4())
    await db_tx.execute(
        """
        INSERT INTO supply_relationships
          (buyer_tenant_id, supplier_tenant_id, supplier_id, material_category, status)
        VALUES ($1,$2,$3,'meat','active'), ($4,$2,$3,'meat','ended')
        """,
        biz_b["tenant_id"],
        biz_a["tenant_id"],
        sid,
        unrelated,
    )

    await upsert_supplier_eligibility(sid, _req(status="revoked"), user=prov_user, db=db_tx)

    rows = await db_tx.fetch("SELECT impacted_tenant_id FROM certificate_risk_alerts WHERE certificate_id=$1", cert["id"])
    assert [str(r["impacted_tenant_id"]) for r in rows] == [biz_b["tenant_id"]]


async def test_invalid_id_400_and_missing_supplier_404(db_tx, biz_a, prov_user):
    await _source_cert(db_tx, biz_a["tenant_id"], prov_user)
    with pytest.raises(HTTPException) as invalid:
        await upsert_supplier_eligibility("not-a-uuid", _req(), user=prov_user, db=db_tx)
    with pytest.raises(HTTPException) as missing:
        await upsert_supplier_eligibility(str(uuid4()), _req(), user=prov_user, db=db_tx)

    assert invalid.value.status_code == 400
    assert missing.value.status_code == 404


async def test_provider_without_active_source_certificate_cannot_authorize_supplier(db_tx, biz_a, prov_user):
    sid = await _supplier(db_tx, biz_a)

    with pytest.raises(HTTPException) as exc:
        await upsert_supplier_eligibility(sid, _req(), user=prov_user, db=db_tx)

    assert exc.value.status_code == 403


async def test_other_provider_cannot_take_over_existing_supplier_eligibility(db_tx, biz_a, prov_user):
    other = await db_tx.fetchrow(
        """
        INSERT INTO users (email, role, company_name, status, tenant_id, is_owner)
        VALUES ($1,'provider','Other CB','active',uuid_generate_v4(),true)
        RETURNING id, email
        """,
        f"other-{uuid4().hex[:8]}@example.com",
    )
    other_user = {"sub": str(other["id"]), "email": other["email"], "role": "provider", "is_owner": True, "tenant_id": str(other["id"])}
    sid = await _supplier(db_tx, biz_a)
    await _source_cert(db_tx, biz_a["tenant_id"], prov_user)
    await _source_cert(db_tx, biz_a["tenant_id"], other_user)
    await upsert_supplier_eligibility(sid, _req(status="active"), user=prov_user, db=db_tx)

    with pytest.raises(HTTPException) as exc:
        await upsert_supplier_eligibility(sid, _req(status="suspended"), user=other_user, db=db_tx)

    assert exc.value.status_code == 403


async def test_business_can_list_and_ack_own_certificate_risk_alerts_only(db_tx, biz_a, biz_b, prov_user):
    sid = await _supplier(db_tx, biz_a)
    cert_id = await _source_cert(db_tx, biz_a["tenant_id"], prov_user)
    cert = await upsert_supplier_eligibility(sid, _req(status="active"), user=prov_user, db=db_tx)
    await db_tx.execute(
        """
        INSERT INTO certificate_risk_alerts
          (impacted_tenant_id, supplier_id, certificate_id, event_type, severity, message)
        VALUES ($1,$2,$3,'revoked','critical','Blocked supplier'),
               ($4,$2,$3,'revoked','critical','Other tenant')
        """,
        biz_a["tenant_id"],
        sid,
        cert["id"],
        biz_b["tenant_id"],
    )

    listed = await list_certificate_risk_alerts(status="open", user=biz_a, db=db_tx)
    assert len(listed["alerts"]) == 1
    assert listed["alerts"][0]["supplier_id"] == sid

    updated = await update_certificate_risk_alert(
        listed["alerts"][0]["id"], CertificateRiskAlertUpdate(status="acknowledged"), user=biz_a, db=db_tx
    )
    assert updated["status"] == "acknowledged"

    with pytest.raises(HTTPException) as exc:
        await update_certificate_risk_alert(listed["alerts"][0]["id"], CertificateRiskAlertUpdate(status="resolved"), user=biz_b, db=db_tx)
    assert exc.value.status_code == 404


async def test_business_cannot_self_authorize_supplier_verified(db_tx, biz_a):
    sid = await _supplier(db_tx, biz_a)

    with pytest.raises(HTTPException) as exc:
        await update_supplier(sid, SupplierUpdate(status="verified"), user=biz_a, db=db_tx)

    assert exc.value.status_code == 400
    assert "CB" in str(exc.value.detail)
