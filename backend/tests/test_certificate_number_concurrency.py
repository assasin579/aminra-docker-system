"""P0 certificate number race/collision regression tests."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeRecord

pytestmark = pytest.mark.asyncio


class DuplicateThenSuccessConn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self.insert_attempts: list[str] = []

    async def fetch(self, sql: str, *args):
        self.calls.append(("fetch", (sql, args)))
        if "FROM submissions WHERE business_tenant" in sql:
            return [FakeRecord(id=uuid4(), status="approved")]
        raise AssertionError(sql)

    async def fetchrow(self, sql: str, *args):
        self.calls.append(("fetchrow", (sql, args)))
        if "SELECT id FROM users WHERE keycloak_sub = $1 OR id = $1 LIMIT 1" in sql:
            return FakeRecord(id=args[0])
        if "FROM halal_certificates WHERE business_tenant=$1 AND issued_by=$2 AND status='active'" in sql:
            return None
        if "FROM users WHERE id=$1" in sql:
            return FakeRecord(company_name="Provider CB")
        if "(id=$1 OR tenant_id=$1) AND is_owner=true" in sql:
            return FakeRecord(id=uuid4(), company_name="Business Co")
        if "INSERT INTO halal_certificates" in sql:
            candidate = args[0]
            self.insert_attempts.append(candidate)
            if len(self.insert_attempts) == 1:
                raise Exception("duplicate key value violates unique constraint halal_certificates_cert_number_key")
            return FakeRecord(id=uuid4())
        raise AssertionError(sql)

    async def fetchval(self, sql: str, *args):
        self.calls.append(("fetchval", (sql, args)))
        if "COUNT(*) FROM halal_certificates WHERE cert_number LIKE" in sql:
            return 7
        raise AssertionError(sql)

    async def execute(self, sql: str, *args):
        self.calls.append(("execute", (sql, args)))
        return None


class TestCertificateNumberConcurrency:
    async def test_issue_certificate_retries_next_number_after_unique_collision(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        import importlib
        from auth import certificate_router

        monkeypatch.setenv("CERT_PDF_DIR", str(tmp_path / "certs"))
        monkeypatch.setenv("APP_BASE_URL", "https://aminra.test")
        importlib.reload(certificate_router)

        db = DuplicateThenSuccessConn()
        provider_id = uuid4()
        result = await certificate_router.issue_certificate_for_company(
            business_tenant_id=str(uuid4()),
            req=certificate_router.IssueCertRequest(expiry_months=12, notes="race test"),
            user={
                "sub": str(provider_id),
                "role": "provider",
                "is_owner": True,
                "tenant_id": str(provider_id),
            },
            db=db,
        )

        assert db.insert_attempts[0].endswith("-0008")
        assert db.insert_attempts[1].endswith("-0009")
        assert result["cert_number"] == db.insert_attempts[1]
        assert (tmp_path / "certs" / f"{result['cert_number']}.pdf").exists()
