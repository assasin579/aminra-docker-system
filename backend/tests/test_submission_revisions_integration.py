"""Integration tests for the revision-cycle endpoints.

Real router functions invoked with real DB connection. Auth + RBAC checks
exercised via FakeRequest + simulated user payloads.
"""
from __future__ import annotations

import os
from uuid import uuid4

import asyncpg
import pytest


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
async def submission_setup(conn):
    """Create a fresh submission + return owner/provider context for endpoint calls."""
    biz = await conn.fetchrow(
        "SELECT id, email, tenant_id, company_name FROM users WHERE role='business' AND is_owner=true LIMIT 1"
    )
    prov = await conn.fetchrow(
        "SELECT id, email, company_name FROM users WHERE role='provider' AND is_owner=true LIMIT 1"
    )
    if not biz or not prov:
        pytest.skip("Need business + provider owner users in DB")

    sub_id = uuid4()
    await conn.execute(
        """
        INSERT INTO submissions (id, business_tenant, provider_id, document_ids, status, company_name)
        VALUES ($1, $2, $3, '{}'::uuid[], 'reviewing', 'Test')
        """,
        sub_id, biz["tenant_id"], prov["id"],
    )

    biz_user = {
        "sub": str(biz["id"]),
        "email": biz["email"],
        "role": "business",
        "is_owner": True,
        "tenant_id": str(biz["tenant_id"]),
    }
    prov_user = {
        "sub": str(prov["id"]),
        "email": prov["email"],
        "role": "provider",
        "is_owner": True,
        "tenant_id": str(prov["id"]),
    }

    yield {
        "submission_id": str(sub_id),
        "biz_user": biz_user,
        "prov_user": prov_user,
    }

    await conn.execute("DELETE FROM submission_revision_requests WHERE submission_id = $1", sub_id)
    await conn.execute("DELETE FROM submissions WHERE id = $1", sub_id)


class _FakeClient:
    host = "10.0.0.1"


class FakeRequest:
    client = _FakeClient()
    headers = {"user-agent": "pytest"}


# ── /received/{id}/request-revision ────────────────────────────────────────

class TestProviderRequestRevisionEndpoint:
    async def test_provider_can_request_revision(self, conn, submission_setup):
        from auth.submission_router import (
            DocumentFeedbackIn, RequestRevisionIn, provider_request_revision,
        )

        ctx = submission_setup
        result = await provider_request_revision(
            submission_id=ctx["submission_id"],
            req=RequestRevisionIn(
                feedback="Cần chứng nhận JAKIM",
                document_feedback=[
                    DocumentFeedbackIn(
                        document_id=str(uuid4()),
                        issue="Thiếu seal",
                        severity="major",
                    ),
                ],
            ),
            request=FakeRequest(),
            user=ctx["prov_user"],
            db=conn,
        )

        assert result["round"] == 1
        # Audit log emitted
        audit_count = await conn.fetchval(
            "SELECT COUNT(*) FROM audit_logs WHERE entity_id = $1 AND action='submission.revision_requested'",
            ctx["submission_id"],
        )
        assert audit_count == 1

    async def test_business_cannot_request_revision(self, conn, submission_setup):
        from fastapi import HTTPException
        from auth.submission_router import RequestRevisionIn, provider_request_revision

        ctx = submission_setup
        with pytest.raises(HTTPException) as exc:
            await provider_request_revision(
                submission_id=ctx["submission_id"],
                req=RequestRevisionIn(feedback="trying"),
                request=FakeRequest(),
                user=ctx["biz_user"],
                db=conn,
            )
        assert exc.value.status_code == 403

    async def test_other_provider_cannot_revise_someone_elses_submission(
        self, conn, submission_setup,
    ):
        from fastapi import HTTPException
        from auth.submission_router import RequestRevisionIn, provider_request_revision

        ctx = submission_setup
        # Build fake "other provider" user
        other_prov = {
            "sub": str(uuid4()),  # not in DB but provider_filter matches by sub
            "email": "other@cb.vn",
            "role": "provider",
            "is_owner": True,
        }
        with pytest.raises(HTTPException) as exc:
            await provider_request_revision(
                submission_id=ctx["submission_id"],
                req=RequestRevisionIn(feedback="forbidden"),
                request=FakeRequest(),
                user=other_prov,
                db=conn,
            )
        assert exc.value.status_code == 404


# ── /{id}/resubmit ────────────────────────────────────────────────────────

class TestBusinessResubmitEndpoint:
    async def test_owner_can_resubmit_after_revision(self, conn, submission_setup):
        from auth.submission_router import (
            RequestRevisionIn, ResubmitIn,
            business_resubmit, provider_request_revision,
        )

        ctx = submission_setup
        # Provider requests revision
        await provider_request_revision(
            submission_id=ctx["submission_id"],
            req=RequestRevisionIn(feedback="fix this"),
            request=FakeRequest(),
            user=ctx["prov_user"],
            db=conn,
        )

        # Business resubmits
        result = await business_resubmit(
            submission_id=ctx["submission_id"],
            req=ResubmitIn(business_notes="Đã sửa"),
            request=FakeRequest(),
            owner=ctx["biz_user"],
            db=conn,
        )

        assert result["round_resolved"] == 1
        sub = await conn.fetchrow(
            "SELECT status FROM submissions WHERE id = $1", ctx["submission_id"],
        )
        assert sub["status"] == "reviewing"

    async def test_other_business_cannot_resubmit(self, conn, submission_setup):
        from fastapi import HTTPException
        from auth.submission_router import (
            RequestRevisionIn, ResubmitIn,
            business_resubmit, provider_request_revision,
        )

        ctx = submission_setup
        await provider_request_revision(
            submission_id=ctx["submission_id"],
            req=RequestRevisionIn(feedback="fix"),
            request=FakeRequest(),
            user=ctx["prov_user"],
            db=conn,
        )

        # Different tenant tries to resubmit
        other_biz = {
            "sub": str(uuid4()),
            "email": "x@other.vn",
            "role": "business",
            "is_owner": True,
            "tenant_id": str(uuid4()),
        }
        with pytest.raises(HTTPException) as exc:
            await business_resubmit(
                submission_id=ctx["submission_id"],
                req=ResubmitIn(),
                request=FakeRequest(),
                owner=other_biz,
                db=conn,
            )
        assert exc.value.status_code == 403


# ── /{id}/revisions ───────────────────────────────────────────────────────

class TestRevisionHistoryEndpoint:
    async def test_business_can_view_history(self, conn, submission_setup):
        from auth.submission_router import (
            RequestRevisionIn, get_revision_history, provider_request_revision,
        )

        ctx = submission_setup
        await provider_request_revision(
            submission_id=ctx["submission_id"],
            req=RequestRevisionIn(feedback="history test"),
            request=FakeRequest(),
            user=ctx["prov_user"],
            db=conn,
        )

        result = await get_revision_history(
            submission_id=ctx["submission_id"],
            user=ctx["biz_user"],
            db=conn,
        )
        assert len(result["history"]) == 1
        assert result["history"][0]["feedback"] == "history test"

    async def test_provider_can_view_history(self, conn, submission_setup):
        from auth.submission_router import (
            RequestRevisionIn, get_revision_history, provider_request_revision,
        )

        ctx = submission_setup
        await provider_request_revision(
            submission_id=ctx["submission_id"],
            req=RequestRevisionIn(feedback="prov view"),
            request=FakeRequest(),
            user=ctx["prov_user"],
            db=conn,
        )

        result = await get_revision_history(
            submission_id=ctx["submission_id"],
            user=ctx["prov_user"],
            db=conn,
        )
        assert len(result["history"]) == 1

    async def test_unrelated_user_blocked(self, conn, submission_setup):
        from fastapi import HTTPException
        from auth.submission_router import get_revision_history

        ctx = submission_setup
        random_biz = {
            "sub": str(uuid4()),
            "email": "x@nope.vn",
            "role": "business",
            "is_owner": True,
            "tenant_id": str(uuid4()),
        }
        with pytest.raises(HTTPException) as exc:
            await get_revision_history(
                submission_id=ctx["submission_id"],
                user=random_biz,
                db=conn,
            )
        assert exc.value.status_code == 403
