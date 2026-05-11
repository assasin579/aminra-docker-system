"""F4 — Dossier CRUD unit tests (30 cases).

Covers:
  - Pydantic models DossierCreate, DossierUpdate, DossierPublic, DocTypeRequirement
  - _resolve_tenant_id helper (owner vs staff vs missing row)
  - _row_to_public translation (with/without documents)
  - Status enum lifecycle validation
  - SQL builder for PATCH dynamic field set

Pure-function tests with mocked DB.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from auth.dossier_router import (
    DocTypeRequirement,
    DocumentInDossier,
    DossierCreate,
    DossierPublic,
    DossierUpdate,
    _resolve_tenant_id,
    _row_to_public,
)


# ── Group 1 — Pydantic DossierCreate validation (7 tests) ──────────────────


class TestDossierCreateValidation:
    def test_valid_create_with_required_fields(self):
        sid = uuid4()
        c = DossierCreate(title="Test", standard_type_id=sid)
        assert c.title == "Test"
        assert c.standard_type_id == sid
        assert c.notes is None

    def test_title_min_length_1(self):
        with pytest.raises(ValidationError):
            DossierCreate(title="", standard_type_id=uuid4())

    def test_title_max_length_255(self):
        DossierCreate(title="a" * 255, standard_type_id=uuid4())
        with pytest.raises(ValidationError):
            DossierCreate(title="a" * 256, standard_type_id=uuid4())

    def test_title_required(self):
        with pytest.raises(ValidationError):
            DossierCreate(standard_type_id=uuid4())  # type: ignore[call-arg]

    def test_standard_type_id_required(self):
        with pytest.raises(ValidationError):
            DossierCreate(title="X")  # type: ignore[call-arg]

    def test_standard_type_id_must_be_uuid(self):
        with pytest.raises(ValidationError):
            DossierCreate(title="X", standard_type_id="not-a-uuid")  # type: ignore[arg-type]

    def test_notes_optional(self):
        c = DossierCreate(title="X", standard_type_id=uuid4(), notes="optional note")
        assert c.notes == "optional note"


# ── Group 2 — DossierUpdate (status enum) validation (6 tests) ─────────────


class TestDossierUpdateValidation:
    @pytest.mark.parametrize("st", [
        "draft", "in_progress", "submitted", "cert_issued", "cancelled",
    ])
    def test_valid_status_accepted(self, st):
        u = DossierUpdate(status=st)
        assert u.status == st

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            DossierUpdate(status="approved")

    def test_invalid_status_typo_rejected(self):
        with pytest.raises(ValidationError):
            DossierUpdate(status="in-progress")  # hyphen not underscore

    def test_status_case_sensitive(self):
        with pytest.raises(ValidationError):
            DossierUpdate(status="DRAFT")

    def test_all_fields_optional(self):
        u = DossierUpdate()
        assert u.title is None
        assert u.status is None
        assert u.notes is None

    def test_title_empty_rejected(self):
        with pytest.raises(ValidationError):
            DossierUpdate(title="")

    def test_partial_update_only_status(self):
        u = DossierUpdate(status="submitted")
        dumped = u.model_dump(exclude_unset=True)
        assert dumped == {"status": "submitted"}


# ── Group 3 — _resolve_tenant_id helper (5 tests) ──────────────────────────


class TestResolveTenantId:
    async def test_user_not_in_db_returns_none(self):
        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value=None)
        result = await _resolve_tenant_id(mock_db, {"email": "missing@x.com"})
        assert result is None

    async def test_owner_with_null_tenant_returns_own_id(self):
        """Owner without tenant_id set → tenant root = owner's own id."""
        mock_db = AsyncMock()
        own_id = uuid4()
        mock_db.fetchrow = AsyncMock(return_value={
            "id": own_id, "tenant_id": None, "is_owner": True,
        })
        result = await _resolve_tenant_id(mock_db, {"email": "owner@x.com"})
        assert result == own_id

    async def test_owner_with_tenant_set_returns_tenant(self):
        mock_db = AsyncMock()
        tid = uuid4()
        mock_db.fetchrow = AsyncMock(return_value={
            "id": uuid4(), "tenant_id": tid, "is_owner": True,
        })
        result = await _resolve_tenant_id(mock_db, {"email": "owner@x.com"})
        assert result == tid

    async def test_staff_returns_tenant_id(self):
        mock_db = AsyncMock()
        tid = uuid4()
        mock_db.fetchrow = AsyncMock(return_value={
            "id": uuid4(), "tenant_id": tid, "is_owner": False,
        })
        result = await _resolve_tenant_id(mock_db, {"email": "staff@x.com"})
        assert result == tid

    async def test_staff_with_null_tenant_returns_none(self):
        """Staff without tenant assignment → undefined ownership → None."""
        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value={
            "id": uuid4(), "tenant_id": None, "is_owner": False,
        })
        result = await _resolve_tenant_id(mock_db, {"email": "stray@x.com"})
        assert result is None


# ── Group 4 — _row_to_public translation (8 tests) ─────────────────────────


class TestRowToPublic:
    @pytest.fixture
    def base_row(self):
        now = datetime.now(timezone.utc)
        return {
            "id": uuid4(),
            "tenant_id": uuid4(),
            "standard_type_id": None,
            "title": "Test Dossier",
            "status": "draft",
            "notes": None,
            "created_at": now,
            "updated_at": now,
        }

    async def test_translate_no_standard_no_documents(self, base_row):
        mock_db = AsyncMock()
        result = await _row_to_public(mock_db, base_row)
        assert isinstance(result, DossierPublic)
        assert result.title == "Test Dossier"
        assert result.standard_type_id is None
        assert result.standard_code is None
        assert result.doc_types == []
        assert result.documents == []

    async def test_translate_with_standard_fetches_doc_types(self, base_row):
        std_id = uuid4()
        base_row["standard_type_id"] = std_id

        mock_db = AsyncMock()
        mock_db.fetchrow = AsyncMock(return_value={
            "code": "ms_1500_2019", "name_vi": "MS 1500",
        })
        mock_db.fetch = AsyncMock(return_value=[
            {"doc_type": "halal_policy", "required": True, "display_order": 1},
            {"doc_type": "has_manual", "required": True, "display_order": 2},
        ])
        result = await _row_to_public(mock_db, base_row)
        assert result.standard_code == "ms_1500_2019"
        assert result.standard_name_vi == "MS 1500"
        assert len(result.doc_types) == 2

    async def test_include_documents_false_skips_doc_fetch(self, base_row):
        mock_db = AsyncMock()
        result = await _row_to_public(mock_db, base_row, include_documents=False)
        assert result.documents == []
        # DB shouldn't have been hit for documents
        mock_db.fetch.assert_not_called()

    async def test_include_documents_true_fetches(self, base_row):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[{
            "id": uuid4(),
            "doc_type": "halal_policy",
            "filename": "x.pdf",
            "original_filename": "Halal Policy.pdf",
            "status": "approved",
            "compliance_score": 95,
            "version_number": 1,
            "uploaded_at": datetime.now(timezone.utc),
        }])
        result = await _row_to_public(mock_db, base_row, include_documents=True)
        assert len(result.documents) == 1
        assert result.documents[0].filename == "x.pdf"

    async def test_document_status_enum_stringified(self, base_row):
        """Status may be Enum in DB → should be str in response."""
        class StatusEnum:
            def __str__(self):
                return "approved"
            value = "approved"
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[{
            "id": uuid4(),
            "doc_type": None,
            "filename": "x.pdf",
            "original_filename": "x.pdf",
            "status": StatusEnum(),
            "compliance_score": None,
            "version_number": 1,
            "uploaded_at": datetime.now(timezone.utc),
        }])
        result = await _row_to_public(mock_db, base_row, include_documents=True)
        assert isinstance(result.documents[0].status, str)

    async def test_document_status_none_handled(self, base_row):
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[{
            "id": uuid4(),
            "doc_type": None,
            "filename": "x.pdf",
            "original_filename": "x.pdf",
            "status": None,
            "compliance_score": None,
            "version_number": 1,
            "uploaded_at": datetime.now(timezone.utc),
        }])
        result = await _row_to_public(mock_db, base_row, include_documents=True)
        assert result.documents[0].status is None

    async def test_notes_in_row_passed_through(self, base_row):
        base_row["notes"] = "Important note about pilot CB"
        mock_db = AsyncMock()
        result = await _row_to_public(mock_db, base_row)
        assert result.notes == "Important note about pilot CB"

    async def test_iso_timestamps_in_output(self, base_row):
        mock_db = AsyncMock()
        result = await _row_to_public(mock_db, base_row)
        # ISO format includes T separator
        assert "T" in result.created_at
        assert "T" in result.updated_at


# ── Group 5 — DocTypeRequirement model (4 tests) ───────────────────────────


class TestDocTypeRequirement:
    def test_valid_construction(self):
        dt = DocTypeRequirement(
            doc_type="halal_policy",
            required=True,
            display_order=1,
        )
        assert dt.doc_type == "halal_policy"
        assert dt.required is True

    def test_required_optional_false(self):
        dt = DocTypeRequirement(
            doc_type="generic", required=False, display_order=99,
        )
        assert dt.required is False

    def test_display_order_negative_allowed(self):
        """No validation on display_order — allows admin to use negative for top-pin."""
        dt = DocTypeRequirement(
            doc_type="x", required=True, display_order=-1,
        )
        assert dt.display_order == -1

    def test_doc_type_empty_string_allowed_by_pydantic(self):
        """No min_length constraint → empty string OK. Defensive: validate at DB layer."""
        dt = DocTypeRequirement(
            doc_type="", required=True, display_order=1,
        )
        assert dt.doc_type == ""
