"""Focused live UAT for certificate issuance and verification.

This is intentionally small and high-signal: it uses real Keycloak demo tokens,
real HTTP routes, and a directly-seeded approved submission so the release gate
proves the critical certificate path instead of relying only on unit fakes.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from tests.test_role_boundaries_live_smoke import _token

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
DEMO_PW = os.getenv("DEMO_PW", "DemoP@ss2026")
PROVIDER_DEMO_PW = os.getenv("PROVIDER_DEMO_PW", DEMO_PW)

pytestmark = pytest.mark.asyncio


def _request(method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, bytes, dict]:
    data = None
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - local/live test URL
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


@pytest.fixture
async def conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


@pytest.fixture
async def approved_demo_submission(conn):
    provider = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE email='cb-demo@demo.aminra.vn' AND role='provider' AND is_owner=true"
    )
    business = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE email='biz-demo-1@demo.aminra.vn' AND role='business' AND is_owner=true"
    )
    if not provider or not business:
        pytest.skip("Demo provider/business users are not seeded")

    # Isolate the happy-path issue action from stale demo data: the endpoint
    # intentionally requires *all* active dossiers for this business/provider to
    # be approved, so preserve then approve existing non-rejected demo rows.
    prior_submissions = await conn.fetch(
        "SELECT id, status FROM submissions WHERE business_tenant=$1 AND provider_id=$2 AND status <> 'rejected'",
        business["tenant_id"],
        provider["id"],
    )
    for row in prior_submissions:
        await conn.execute("UPDATE submissions SET status='approved' WHERE id=$1", row["id"])

    # Ensure the happy-path issue action is not blocked by an old active cert from
    # a previous manual/demo run. We preserve historical/revoked rows and restore
    # the active statuses after the test.
    prior_active_certs = await conn.fetch(
        "SELECT id, status FROM halal_certificates WHERE business_tenant=$1 AND issued_by=$2 AND status='active'",
        business["tenant_id"],
        provider["id"],
    )
    await conn.execute(
        "UPDATE halal_certificates SET status='suspended', updated_at=NOW() "
        "WHERE business_tenant=$1 AND issued_by=$2 AND status='active'",
        business["tenant_id"],
        provider["id"],
    )

    submission_id = uuid4()
    await conn.execute(
        """
        INSERT INTO submissions
            (id, business_tenant, provider_id, document_ids,
             revision_round, sla_alerts_sent, status)
        VALUES ($1, $2, $3, '{}'::uuid[], 0, '{}'::jsonb, 'approved')
        """,
        submission_id,
        business["tenant_id"],
        provider["id"],
    )
    state = {
        "submission_id": str(submission_id),
        "business_tenant": str(business["tenant_id"]),
        "provider_id": str(provider["id"]),
        "created_cert_id": None,
    }
    try:
        yield state
    finally:
        created_cert_id = state.get("created_cert_id")
        if created_cert_id:
            row = await conn.fetchrow("SELECT pdf_path FROM halal_certificates WHERE id=$1", created_cert_id)
            await conn.execute("DELETE FROM halal_certificates WHERE id=$1", created_cert_id)
            if row and row["pdf_path"]:
                Path(row["pdf_path"]).unlink(missing_ok=True)
        await conn.execute("DELETE FROM submissions WHERE id=$1", submission_id)
        for row in prior_submissions:
            await conn.execute("UPDATE submissions SET status=$1 WHERE id=$2", row["status"], row["id"])
        for row in prior_active_certs:
            await conn.execute("UPDATE halal_certificates SET status=$1, updated_at=NOW() WHERE id=$2", row["status"], row["id"])


async def test_provider_can_issue_pdf_business_can_download_and_public_can_verify(approved_demo_submission):
    provider_token = _token("cb-demo@demo.aminra.vn", PROVIDER_DEMO_PW)
    business_token = _token("biz-demo-1@demo.aminra.vn", DEMO_PW)

    status, raw, _ = _request(
        "POST",
        f"/api/submissions/issue-certificate/{approved_demo_submission['business_tenant']}",
        provider_token,
        {"expiry_months": 12, "notes": "live UAT certificate issuance"},
    )
    assert status == 200, raw[:500]
    issued = json.loads(raw)
    cert_id = issued["id"]
    cert_number = issued["cert_number"]
    approved_demo_submission["created_cert_id"] = cert_id
    assert cert_number.startswith("HALAL-")
    assert issued["pdf_url"].endswith(f"/certificates/{cert_id}/pdf")

    pdf_status, pdf_raw, pdf_headers = _request(
        "GET",
        f"/api/submissions/certificates/{cert_id}/pdf",
        business_token,
    )
    assert pdf_status == 200, pdf_raw[:500]
    content_type = pdf_headers.get("Content-Type") or pdf_headers.get("content-type", "")
    assert content_type.startswith("application/pdf")
    assert pdf_raw.startswith(b"%PDF")

    verify_status, verify_raw, _ = _request(
        "GET",
        f"/api/submissions/certificates/public/{urllib.parse.quote(cert_number)}",
    )
    assert verify_status == 200, verify_raw[:500]
    public_body = json.loads(verify_raw)
    assert public_body["cert_number"] == cert_number
    assert public_body["status"] == "active"
    assert public_body["valid"] is True
    assert "pdf_path" not in public_body
    assert "business_tenant" not in public_body
    assert "revoked_by" not in public_body
