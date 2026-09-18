from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from auth.identity import get_or_reconcile_user_from_keycloak_claims, resolve_canonical_user_id


class Row(dict):
    pass


class FakeDB:
    def __init__(self, *, row_by_sub=None, row_by_email=None):
        self.row_by_sub = row_by_sub
        self.row_by_email = row_by_email
        self.updated = []
        self.inserted = []

    async def fetchrow(self, query, *args):
        compact = " ".join(query.split())
        if "SELECT * FROM users WHERE keycloak_sub" in compact:
            return self.row_by_sub
        if "SELECT * FROM users WHERE lower(email)" in compact:
            return self.row_by_email
        if compact.startswith("UPDATE users SET tenant_id = id"):
            row = self.row_by_sub or self.row_by_email
            assert row is not None
            row = Row(dict(row))
            row["tenant_id"] = row["id"]
            self.updated.append((compact, args))
            self.row_by_email = row
            return row
        if compact.startswith("UPDATE users SET") and "RETURNING *" in compact:
            target_id = args[-1]
            row = self.row_by_sub or self.row_by_email
            assert row is not None
            updated = Row(dict(row))
            if "keycloak_sub" in compact:
                updated["keycloak_sub"] = args[0]
            if "status" in compact:
                updated["status"] = "active"
            if "is_owner" in compact:
                updated["is_owner"] = True
            self.updated.append((compact, args))
            if updated["id"] == target_id:
                self.row_by_email = updated
                return updated
        if compact.startswith("INSERT INTO users"):
            row = Row(
                id=uuid.uuid4(),
                email=args[0],
                keycloak_sub=args[1],
                role=args[2],
                company_name=args[3],
                status=args[4],
                is_owner=args[5],
                tenant_id=args[6],
                industry_schema_id=None,
            )
            self.inserted.append(row)
            self.row_by_email = row
            return row
        if "SELECT id FROM users" in compact:
            row = self.row_by_sub or self.row_by_email
            return Row(id=row["id"]) if row else None
        raise AssertionError(f"unexpected query: {compact}")


@pytest.mark.asyncio
async def test_reconcile_stale_keycloak_sub_and_owner_tenant():
    app_id = uuid.uuid4()
    old_sub = uuid.uuid4()
    new_sub = uuid.uuid4()
    db = FakeDB(
        row_by_sub=None,
        row_by_email=Row(
            id=app_id,
            email="owner@example.com",
            keycloak_sub=old_sub,
            role="business",
            status="pending",
            is_owner=False,
            tenant_id=None,
            industry_schema_id=None,
        ),
    )

    row = await get_or_reconcile_user_from_keycloak_claims(
        {
            "_keycloak": True,
            "sub": str(app_id),  # legacy app-id shape from fallback enrichment
            "keycloak_sub": str(new_sub),
            "email": "OWNER@example.com",
            "role": "business",
            "status": "active",
            "is_owner": True,
        },
        db,
    )

    assert row["id"] == app_id
    assert row["keycloak_sub"] == new_sub
    assert row["status"] == "active"
    assert row["is_owner"] is True
    assert row["tenant_id"] == app_id
    assert db.updated


@pytest.mark.asyncio
async def test_reconcile_fails_closed_when_subject_and_email_disagree():
    db = FakeDB(
        row_by_sub=Row(id=uuid.uuid4(), email="a@example.com", keycloak_sub=uuid.uuid4()),
        row_by_email=Row(id=uuid.uuid4(), email="b@example.com", keycloak_sub=uuid.uuid4()),
    )

    with pytest.raises(HTTPException) as exc:
        await get_or_reconcile_user_from_keycloak_claims(
            {"_keycloak": True, "keycloak_sub": str(uuid.uuid4()), "email": "b@example.com"},
            db,
        )

    assert exc.value.status_code == 409
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail["code"] == "identity_state_conflict"


@pytest.mark.asyncio
async def test_resolve_canonical_user_id_never_returns_keycloak_sub():
    app_id = uuid.uuid4()
    kc_sub = uuid.uuid4()
    db = FakeDB(row_by_email=Row(id=app_id, email="u@example.com", keycloak_sub=kc_sub, role="business", status="active", is_owner=True, tenant_id=app_id))

    resolved = await resolve_canonical_user_id(
        {"_keycloak": True, "sub": str(kc_sub), "keycloak_sub": str(kc_sub), "email": "u@example.com"},
        db,
    )

    assert resolved == app_id
    assert resolved != kc_sub
