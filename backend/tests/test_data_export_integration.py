"""Integration tests for the GET /me/export-data endpoint.

Verifies the wire (auth → service → audit log → response). The unit-level
suite already covers bundle shape and secret filtering.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from tests.test_data_export_unit import _build_business_db, USER_ID, TENANT_ID


class _FakeClient:
    host = "10.0.0.1"


class FakeRequest:
    client = _FakeClient()
    headers = {"user-agent": "pytest"}


class TestExportEndpoint:
    async def test_returns_json_attachment_response(self):
        from auth.gdpr_router import export_my_data

        user = {
            "sub": USER_ID, "email": "biz@example.vn",
            "role": "business", "tenant_id": TENANT_ID,
        }
        resp = await export_my_data(
            request=FakeRequest(),
            user=user,
            db=_build_business_db(),
            _=None,
        )

        assert resp.media_type == "application/json"
        cd = resp.headers["content-disposition"]
        assert cd.startswith("attachment;")
        assert "aminra-export-" in cd
        assert ".json" in cd
        assert resp.headers["x-export-format-version"] == "1.0"

    async def test_response_body_is_valid_complete_bundle(self):
        from auth.gdpr_router import export_my_data

        user = {
            "sub": USER_ID, "email": "biz@example.vn",
            "role": "business", "tenant_id": TENANT_ID,
        }
        resp = await export_my_data(
            request=FakeRequest(),
            user=user,
            db=_build_business_db(),
            _=None,
        )
        body = json.loads(resp.body.decode("utf-8"))
        assert body["user_id"] == USER_ID
        assert "data_subject" in body
        assert body["data_subject"]["profile"]["email"] == "biz@example.vn"

    async def test_emits_audit_log_with_section_counts(self):
        from auth.gdpr_router import export_my_data

        user = {
            "sub": USER_ID, "email": "biz@example.vn",
            "role": "business", "tenant_id": TENANT_ID,
        }
        db = _build_business_db()
        await export_my_data(request=FakeRequest(), user=user, db=db, _=None)

        # Find the audit log INSERT
        audit_inserts = [args for kind, (sql, args) in db.calls
                         if kind == "execute" and "INSERT INTO audit_logs" in sql]
        assert len(audit_inserts) == 1
        args = audit_inserts[0]
        assert args[4] == "data.export.requested"
        assert args[5] == "user"
        assert args[6] == USER_ID

        meta = json.loads(args[8])
        assert meta["byte_size"] > 0
        assert meta["section_counts"]["notifications"] == 1
        assert meta["section_counts"]["certificates"]  == 1

    async def test_filename_includes_date_and_user_prefix(self):
        from auth.gdpr_router import export_my_data

        user = {
            "sub": USER_ID, "email": "biz@example.vn",
            "role": "business", "tenant_id": TENANT_ID,
        }
        resp = await export_my_data(
            request=FakeRequest(),
            user=user,
            db=_build_business_db(),
            _=None,
        )
        cd = resp.headers["content-disposition"]
        # Filename format: aminra-export-{user[:8]}-{YYYYMMDD-HHMMSS}.json
        today = datetime.utcnow().strftime("%Y%m%d")
        assert today in cd
        assert USER_ID[:8] in cd
