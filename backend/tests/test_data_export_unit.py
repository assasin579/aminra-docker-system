"""Unit tests for services/data_export.py — verify the bundle shape and that
secrets never leak into the export.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


USER_ID   = str(uuid4())
TENANT_ID = str(uuid4())


def _build_business_db():
    db = FakeConn()
    db.fetchrow_responses = [
        ("FROM users WHERE id = $1", FakeRecord(
            id=USER_ID,
            email="biz@example.vn",
            role="business",
            status="active",
            company_name="Halal Foods Co",
            company_code="HF001",
            is_owner=True,
            tenant_id=TENANT_ID,
            address="123 Le Loi",
            phone="+84 901234567",
            representative_name="Mr. Tuan",
            password_hash="$2b$12$NEVER_SHOW_THIS",  # MUST be filtered
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            approved_at=None,
            approved_by=None,
        )),
    ]
    db.fetch_responses = [
        # notifications
        ("FROM notifications WHERE user_id", [
            FakeRecord(
                id=uuid4(), type="cert", title="Cert issued", message="…",
                link="/dashboard", read=False,
                created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            ),
        ]),
        # audit_logs (user-owned)
        ("FROM audit_logs WHERE user_id", [
            FakeRecord(
                id=uuid4(), action="login.success", entity_type="user",
                entity_id=USER_ID, changes=None,
                metadata=json.dumps({"ip": "1.2.3.4"}),
                created_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
            ),
        ]),
        # documents
        ("FROM documents WHERE tenant_id", [
            FakeRecord(id=uuid4(), filename="halal-cert.pdf",
                       doc_type="halal_application", status="approved",
                       uploaded_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
        ]),
        # submissions
        ("FROM submissions WHERE business_tenant", [
            FakeRecord(id=uuid4(), provider_id=uuid4(),
                       document_ids=[uuid4()], status="approved",
                       notes="", company_name="Halal Foods Co",
                       submitted_at=datetime(2026, 3, 5, tzinfo=timezone.utc),
                       updated_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
                       auditor_notes=""),
        ]),
        # certificates
        ("FROM halal_certificates WHERE business_tenant", [
            FakeRecord(id=uuid4(), cert_number="HALAL-2026-0001",
                       issued_by=uuid4(), company_name="Halal Foods Co",
                       issue_date=datetime(2026, 4, 1).date(),
                       expiry_date=datetime(2027, 4, 1).date(),
                       status="active", notes="",
                       created_at=datetime(2026, 4, 1, tzinfo=timezone.utc)),
        ]),
        # audit_visits
        ("FROM audit_visits WHERE business_tenant", []),
        # suppliers
        ("FROM suppliers WHERE tenant_id", []),
        # materials
        ("FROM materials WHERE tenant_id", []),
        # production_batches
        ("FROM production_batches WHERE tenant_id", []),
    ]
    return db


# ── Bundle shape ────────────────────────────────────────────────────────────

class TestBundleShape:
    async def test_top_level_keys(self):
        from services.data_export import export_user_data

        bundle = await export_user_data(_build_business_db(), {
            "sub": USER_ID, "email": "biz@example.vn",
            "role": "business", "tenant_id": TENANT_ID,
        })
        assert set(bundle.keys()) == {
            "export_format_version", "exported_at", "user_id",
            "data_subject", "tenant_data", "provider_data",
            "legal_basis", "retention_note",
        }
        assert bundle["user_id"] == USER_ID

    async def test_legal_basis_mentions_both_jurisdictions(self):
        from services.data_export import export_user_data
        bundle = await export_user_data(_build_business_db(), {
            "sub": USER_ID, "tenant_id": TENANT_ID, "role": "business",
        })
        assert "Nghị định 13" in bundle["legal_basis"]["vietnam"]
        assert "Article 20" in bundle["legal_basis"]["eu_gdpr"]

    async def test_data_subject_section_has_profile_notifs_audits(self):
        from services.data_export import export_user_data
        bundle = await export_user_data(_build_business_db(), {
            "sub": USER_ID, "tenant_id": TENANT_ID, "role": "business",
        })
        ds = bundle["data_subject"]
        assert ds["profile"]["email"] == "biz@example.vn"
        assert len(ds["notifications"]) == 1
        assert len(ds["audit_logs"]) == 1


# ── Secret filtering ────────────────────────────────────────────────────────

class TestSecretFiltering:
    async def test_password_hash_never_appears(self):
        from services.data_export import export_user_data
        bundle = await export_user_data(_build_business_db(), {
            "sub": USER_ID, "tenant_id": TENANT_ID, "role": "business",
        })
        as_text = json.dumps(bundle)
        assert "password_hash" not in as_text
        assert "$2b$" not in as_text

    async def test_audit_log_metadata_parsed_to_object_not_string(self):
        from services.data_export import export_user_data
        bundle = await export_user_data(_build_business_db(), {
            "sub": USER_ID, "tenant_id": TENANT_ID, "role": "business",
        })
        log_entry = bundle["data_subject"]["audit_logs"][0]
        assert isinstance(log_entry["metadata"], dict)
        assert log_entry["metadata"]["ip"] == "1.2.3.4"


# ── JSON-serializability ────────────────────────────────────────────────────

class TestJsonSerializable:
    async def test_full_bundle_round_trips_through_json(self):
        from services.data_export import export_user_data
        bundle = await export_user_data(_build_business_db(), {
            "sub": USER_ID, "tenant_id": TENANT_ID, "role": "business",
        })
        # Should not raise
        text = json.dumps(bundle, ensure_ascii=False)
        # And re-parses to the same shape
        reparsed = json.loads(text)
        assert reparsed["user_id"] == USER_ID

    async def test_datetimes_serialized_as_iso_strings(self):
        from services.data_export import export_user_data
        bundle = await export_user_data(_build_business_db(), {
            "sub": USER_ID, "tenant_id": TENANT_ID, "role": "business",
        })
        # Profile.created_at must be an ISO string, not a datetime object
        assert isinstance(bundle["data_subject"]["profile"]["created_at"], str)
        assert bundle["data_subject"]["profile"]["created_at"].startswith("2026-01-01")


# ── Tenant + provider scoping ───────────────────────────────────────────────

class TestRoleScoping:
    async def test_business_role_no_provider_data(self):
        from services.data_export import export_user_data
        bundle = await export_user_data(_build_business_db(), {
            "sub": USER_ID, "tenant_id": TENANT_ID, "role": "business",
        })
        # provider_data section is empty for non-provider users
        assert bundle["provider_data"] == {}

    async def test_user_with_no_tenant_id_skips_tenant_section(self):
        from services.data_export import export_user_data
        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM users WHERE id = $1", FakeRecord(
                id=USER_ID, email="solo@example.vn", role="business",
                status="active", company_name="Solo", company_code="X",
                is_owner=False, tenant_id=None,
                address=None, phone=None, representative_name=None,
                password_hash="$2b$12$xxx",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                approved_at=None, approved_by=None,
            )),
        ]
        db.fetch_responses = [
            ("FROM notifications WHERE user_id", []),
            ("FROM audit_logs WHERE user_id", []),
        ]
        bundle = await export_user_data(db, {
            "sub": USER_ID, "role": "business", "tenant_id": None,
        })
        assert bundle["tenant_data"] == {}


# ── Validation ──────────────────────────────────────────────────────────────

class TestValidation:
    async def test_missing_sub_raises(self):
        from services.data_export import export_user_data
        with pytest.raises(ValueError, match="user is required"):
            await export_user_data(FakeConn(), {})

    async def test_none_user_raises(self):
        from services.data_export import export_user_data
        with pytest.raises(ValueError, match="user is required"):
            await export_user_data(FakeConn(), None)
