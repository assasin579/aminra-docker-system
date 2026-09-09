"""Regression tests for invite flows writing AMINRA-canonical `invited_by`.

Keycloak JWT `sub` is the IdP user UUID. The `users.invited_by` column is a
foreign key to AMINRA `users.id`, so invite routes must resolve the actor's
canonical app user id before inserting child member/auditor rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from auth.models import InviteAuditorRequest, InviteMemberRequest
from auth.router import invite_auditor, invite_member, remove_auditor, remove_member


class _FakeDB:
    def __init__(self, *, canonical_user_id: uuid.UUID, delete_kc_sub: uuid.UUID | None = None):
        self.canonical_user_id = canonical_user_id
        self.delete_kc_sub = delete_kc_sub
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetchval_calls: list[tuple[str, tuple]] = []
        self.execute_calls: list[tuple[str, tuple]] = []
        self.insert_args: tuple | None = None

    async def fetchval(self, query: str, *args):
        self.fetchval_calls.append((query, args))
        if "COUNT(*)" in query:
            return 0
        if "SELECT id FROM users WHERE email" in query:
            return None
        raise AssertionError(f"Unexpected fetchval query: {query}")

    async def fetchrow(self, query: str, *args):
        self.fetchrow_calls.append((query, args))
        if "SELECT id FROM users WHERE keycloak_sub" in query:
            return {"id": self.canonical_user_id}
        if "SELECT keycloak_sub FROM users" in query:
            return {"keycloak_sub": self.delete_kc_sub}
        if "INSERT INTO users" in query:
            self.insert_args = args
            return {
                "id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                "email": args[0],
                "company_name": args[2],
                "status": "active",
                "created_at": datetime.now(timezone.utc),
            }
        raise AssertionError(f"Unexpected fetchrow query: {query}")

    async def execute(self, query: str, *args):
        self.execute_calls.append((query, args))
        return "DELETE 1" if "DELETE FROM users" in query else "UPDATE 1"


@pytest.fixture
def keycloak_stub(monkeypatch):
    created: list[dict] = []
    deleted: list[str] = []

    def fake_create_user(**kwargs):
        created.append(kwargs)
        return "33333333-3333-3333-3333-333333333333"

    def fake_delete_user(kc_sub: str):
        deleted.append(kc_sub)

    monkeypatch.setattr("auth.router.keycloak_admin.create_user", fake_create_user)
    monkeypatch.setattr("auth.router.keycloak_admin.delete_user", fake_delete_user)
    return {"created": created, "deleted": deleted}


@pytest.mark.asyncio
async def test_business_invite_writes_invited_by_as_canonical_aminra_user_id(keycloak_stub):
    canonical_owner_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    keycloak_sub = "22222222-2222-2222-2222-222222222222"
    tenant_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    db = _FakeDB(canonical_user_id=canonical_owner_id)

    await invite_member(
        InviteMemberRequest(
            email="qa-member-canonical@example.com",
            password="Canonical2026!",
            display_name="QA Canonical Member",
            ihc_role="IHC",
            department="QA",
        ),
        owner={
            "sub": keycloak_sub,
            "email": "owner@example.com",
            "role": "business",
            "is_owner": True,
            "tenant_id": tenant_id,
            "_keycloak": True,
        },
        db=db,
    )

    assert db.insert_args is not None
    assert db.insert_args[4] == canonical_owner_id
    assert db.insert_args[4] != keycloak_sub


@pytest.mark.asyncio
async def test_provider_auditor_invite_writes_invited_by_as_canonical_aminra_user_id(keycloak_stub):
    canonical_owner_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    keycloak_sub = "66666666-6666-6666-6666-666666666666"
    tenant_id = uuid.UUID("77777777-7777-7777-7777-777777777777")
    db = _FakeDB(canonical_user_id=canonical_owner_id)

    await invite_auditor(
        InviteAuditorRequest(
            email="qa-auditor-canonical@example.com",
            password="Canonical2026!",
            display_name="QA Canonical Auditor",
            specialty="Halal compliance",
        ),
        owner={
            "sub": keycloak_sub,
            "email": "provider-owner@example.com",
            "role": "provider",
            "is_owner": True,
            "tenant_id": tenant_id,
            "_keycloak": True,
        },
        db=db,
    )

    assert db.insert_args is not None
    assert db.insert_args[4] == canonical_owner_id
    assert db.insert_args[4] != keycloak_sub


@pytest.mark.asyncio
async def test_business_member_delete_removes_keycloak_account_before_pg_row(keycloak_stub):
    member_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    member_kc_sub = uuid.UUID("88888888-8888-8888-8888-888888888888")
    tenant_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    db = _FakeDB(
        canonical_user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        delete_kc_sub=member_kc_sub,
    )

    await remove_member(
        member_id,
        owner={"tenant_id": tenant_id, "sub": "22222222-2222-2222-2222-222222222222"},
        db=db,
    )

    assert keycloak_stub["deleted"] == [str(member_kc_sub)]
    assert db.execute_calls
    assert "DELETE FROM users" in db.execute_calls[-1][0]


@pytest.mark.asyncio
async def test_provider_auditor_delete_removes_keycloak_account_before_pg_row(keycloak_stub):
    auditor_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    auditor_kc_sub = uuid.UUID("99999999-9999-9999-9999-999999999999")
    tenant_id = uuid.UUID("77777777-7777-7777-7777-777777777777")
    db = _FakeDB(
        canonical_user_id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
        delete_kc_sub=auditor_kc_sub,
    )

    await remove_auditor(
        auditor_id,
        owner={"tenant_id": tenant_id, "sub": "66666666-6666-6666-6666-666666666666"},
        db=db,
    )

    assert keycloak_stub["deleted"] == [str(auditor_kc_sub)]
    assert db.execute_calls
    assert "DELETE FROM users" in db.execute_calls[-1][0]
