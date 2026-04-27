"""Integration tests for cert issuance.

Wires the real FastAPI route against a fake asyncpg-style Connection so we
exercise validation, hash, PDF generation, filesystem write, and response
shape — without needing a running container or test DB.

Unit tests cover PDF rendering details; this layer catches integration
regressions: forgot to await, wrong field name in INSERT, PDF written but
path not stored, etc.
"""
from __future__ import annotations

import os
from datetime import date, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import fitz  # pymupdf
import pytest


# ── Fake asyncpg.Connection ─────────────────────────────────────────────────

class FakeRecord(dict):
    """asyncpg.Record-like — supports row["foo"] AND row.get("foo")."""


class FakeConn:
    """Minimal stub matching asyncpg.Connection used by the router."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        # Each script is a list of (sql_substring, return_value) pairs.
        # The first matching substring wins, like a tiny query router.
        self.fetch_responses: list[tuple[str, list]] = []
        self.fetchrow_responses: list[tuple[str, FakeRecord | None]] = []
        self.fetchval_responses: list[tuple[str, Any]] = []

    def _match(self, sql: str, table: list[tuple[str, Any]]) -> Any:
        for needle, value in table:
            if needle in sql:
                return value
        raise AssertionError(f"No FakeConn response configured for: {sql[:80]!r}")

    async def fetch(self, sql: str, *args):
        self.calls.append(("fetch", (sql, args)))
        return self._match(sql, self.fetch_responses)

    async def fetchrow(self, sql: str, *args):
        self.calls.append(("fetchrow", (sql, args)))
        return self._match(sql, self.fetchrow_responses)

    async def fetchval(self, sql: str, *args):
        self.calls.append(("fetchval", (sql, args)))
        return self._match(sql, self.fetchval_responses)

    async def execute(self, sql: str, *args):
        self.calls.append(("execute", (sql, args)))
        return None


# ── Fixtures ────────────────────────────────────────────────────────────────

PROVIDER_USER_ID = uuid4()
PROVIDER_TENANT_ID = uuid4()
BUSINESS_TENANT_ID = uuid4()
BUSINESS_OWNER_ID = uuid4()


@pytest.fixture
def cert_pdf_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CERT_PDF_DIR", str(tmp_path / "certs"))
    monkeypatch.setenv("APP_BASE_URL", "https://aminra.test")
    # Reload module-level CERT_PDF_DIR
    import importlib
    from auth import certificate_router
    importlib.reload(certificate_router)
    return tmp_path / "certs"


@pytest.fixture
def provider_user() -> dict:
    return {
        "sub": str(PROVIDER_USER_ID),
        "role": "provider",
        "is_owner": True,
        "tenant_id": str(PROVIDER_TENANT_ID),
    }


@pytest.fixture
def happy_path_db() -> FakeConn:
    """All submissions approved, no existing cert, biz owner found."""
    db = FakeConn()
    db.fetch_responses = [
        ("FROM submissions WHERE business_tenant", [
            FakeRecord(id=uuid4(), status="approved"),
            FakeRecord(id=uuid4(), status="approved"),
        ]),
    ]
    db.fetchrow_responses = [
        # No existing active cert
        ("FROM halal_certificates WHERE business_tenant=$1 AND issued_by=$2 AND status='active'",
         None),
        # Provider name lookup
        ("FROM users WHERE id=$1", FakeRecord(company_name="Halal CB Vietnam")),
        # Business owner lookup (used twice — name + notify)
        ("(id=$1 OR tenant_id=$1) AND is_owner=true",
         FakeRecord(id=BUSINESS_OWNER_ID, company_name="Halal Foods Co")),
        # INSERT cert RETURNING id
        ("INSERT INTO halal_certificates", FakeRecord(id=uuid4())),
    ]
    db.fetchval_responses = [
        ("COUNT(*) FROM halal_certificates WHERE cert_number LIKE", 7),
    ]
    return db


# ── Tests ───────────────────────────────────────────────────────────────────

class TestIssueCertificateEndpoint:
    async def test_happy_path_writes_pdf_and_returns_cert_number(
        self,
        cert_pdf_dir: Path,
        provider_user: dict,
        happy_path_db: FakeConn,
    ):
        from auth.certificate_router import issue_certificate_for_company, IssueCertRequest

        result = await issue_certificate_for_company(
            business_tenant_id=str(BUSINESS_TENANT_ID),
            req=IssueCertRequest(expiry_months=12, notes="MVP test"),
            user=provider_user,
            db=happy_path_db,
        )

        # Response shape
        year = date.today().year
        expected_cert_number = f"HALAL-{year}-0008"  # count was 7 → next is 8
        assert result["cert_number"] == expected_cert_number
        assert result["issue_date"] == date.today().isoformat()
        assert "id" in result

        # Filesystem
        pdf_file = cert_pdf_dir / f"{expected_cert_number}.pdf"
        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 1000

        # PDF content sanity check — service did the right thing
        with fitz.open(pdf_file) as doc:
            text = "\n".join(p.get_text() for p in doc)
        assert expected_cert_number in text
        assert "Halal Foods Co" in text
        assert "Halal CB Vietnam" in text
        assert "MVP test" in text

    async def test_rejects_non_provider_owner(
        self, cert_pdf_dir: Path, happy_path_db: FakeConn
    ):
        from fastapi import HTTPException
        from auth.certificate_router import issue_certificate_for_company, IssueCertRequest

        biz_user = {"sub": str(uuid4()), "role": "business", "is_owner": True}
        with pytest.raises(HTTPException) as exc:
            await issue_certificate_for_company(
                business_tenant_id=str(BUSINESS_TENANT_ID),
                req=IssueCertRequest(),
                user=biz_user,
                db=happy_path_db,
            )
        assert exc.value.status_code == 403

    async def test_rejects_when_some_submissions_unapproved(
        self, cert_pdf_dir: Path, provider_user: dict
    ):
        from fastapi import HTTPException
        from auth.certificate_router import issue_certificate_for_company, IssueCertRequest

        db = FakeConn()
        db.fetch_responses = [
            ("FROM submissions WHERE business_tenant", [
                FakeRecord(id=uuid4(), status="approved"),
                FakeRecord(id=uuid4(), status="reviewing"),  # not approved
            ]),
        ]
        with pytest.raises(HTTPException) as exc:
            await issue_certificate_for_company(
                business_tenant_id=str(BUSINESS_TENANT_ID),
                req=IssueCertRequest(),
                user=provider_user,
                db=db,
            )
        assert exc.value.status_code == 400
        assert "chưa được duyệt" in exc.value.detail

    async def test_rejects_when_active_cert_already_exists(
        self, cert_pdf_dir: Path, provider_user: dict
    ):
        from fastapi import HTTPException
        from auth.certificate_router import issue_certificate_for_company, IssueCertRequest

        db = FakeConn()
        db.fetch_responses = [
            ("FROM submissions WHERE business_tenant", [
                FakeRecord(id=uuid4(), status="approved"),
            ]),
        ]
        db.fetchrow_responses = [
            ("FROM halal_certificates WHERE business_tenant=$1 AND issued_by=$2 AND status='active'",
             FakeRecord(id=uuid4(), cert_number="HALAL-2026-0001")),
        ]
        with pytest.raises(HTTPException) as exc:
            await issue_certificate_for_company(
                business_tenant_id=str(BUSINESS_TENANT_ID),
                req=IssueCertRequest(),
                user=provider_user,
                db=db,
            )
        assert exc.value.status_code == 400
        assert "HALAL-2026-0001" in exc.value.detail

    async def test_pdf_contains_qr_with_verify_url_pointing_at_app_base(
        self,
        cert_pdf_dir: Path,
        provider_user: dict,
        happy_path_db: FakeConn,
    ):
        from auth.certificate_router import issue_certificate_for_company, IssueCertRequest
        from PIL import Image
        from io import BytesIO
        from services.certificate_pdf import _build_qr_png

        result = await issue_certificate_for_company(
            business_tenant_id=str(BUSINESS_TENANT_ID),
            req=IssueCertRequest(),
            user=provider_user,
            db=happy_path_db,
        )

        # Re-derive the QR pattern we expect
        expected_url = f"https://aminra.test/verify/{result['cert_number']}"
        expected_grid = _qr_grid(_build_qr_png(expected_url))

        pdf_file = cert_pdf_dir / f"{result['cert_number']}.pdf"
        with fitz.open(pdf_file) as doc:
            for page in doc:
                for img_info in page.get_images(full=True):
                    embedded = doc.extract_image(img_info[0])["image"]
                    if _qr_grid(embedded) == expected_grid:
                        return  # match found
        pytest.fail("QR in saved PDF does not encode the expected verify URL")


def _qr_grid(png_bytes: bytes) -> tuple:
    from PIL import Image
    from io import BytesIO
    img = Image.open(BytesIO(png_bytes)).convert("1").resize((25, 25), Image.NEAREST)
    return tuple(img.getdata())
