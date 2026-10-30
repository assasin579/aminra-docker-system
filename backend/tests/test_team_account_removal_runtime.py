"""Real PostgreSQL deletion boundaries; every test rolls back its own QA rows."""

import importlib.util
import os
from uuid import uuid4

import asyncpg
import pytest
from fastapi import HTTPException


@pytest.fixture
def removal():
    candidate = os.getenv("TEAM_REMOVAL_MODULE_PATH")
    if candidate:
        spec = importlib.util.spec_from_file_location("removal_candidate", candidate)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    from auth import team_account_removal
    return team_account_removal


@pytest.fixture
async def account():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL required for real PostgreSQL rollback tests")
    db = await asyncpg.connect(url)
    tx = db.transaction()
    await tx.start()
    owner, member, identity = uuid4(), uuid4(), uuid4()
    try:
        await db.execute(
            "INSERT INTO users (id,email,role,company_name,status,tenant_id,is_owner) "
            "VALUES ($1,$2,'provider','QA removal owner','active',$1,true)",
            owner, f"qa-removal-{owner}@example.com",
        )
        await db.execute(
            "INSERT INTO users (id,email,role,company_name,status,tenant_id,is_owner,keycloak_sub) "
            "VALUES ($1,$2,'provider','QA removal member','active',$3,false,$4)",
            member, f"qa-removal-{member}@example.com", owner, identity,
        )
        notification = await db.fetchval(
            "INSERT INTO notifications (user_id,type,title) "
            "VALUES ($1,'qa_removal','rollback fixture') RETURNING id", member,
        )
        yield db, owner, member, identity, notification
    finally:
        await tx.rollback()
        await db.close()


async def test_audit_history_returns_conflict_before_keycloak(account, removal, monkeypatch):
    db, owner, member, _, notification = account
    log_id = await db.fetchval(
        "INSERT INTO audit_logs (user_id,action,entity_type,entity_id) "
        "VALUES ($1,'qa.removal','user',$1) RETURNING id", member,
    )
    calls = []
    monkeypatch.setattr(removal.keycloak_admin, "delete_user", calls.append)
    with pytest.raises(HTTPException) as exc:
        await removal.remove_team_account(db, user_id=member, tenant_id=owner, provider_only=True)
    assert exc.value.status_code == 409
    assert calls == []
    assert await db.fetchval("SELECT user_id FROM audit_logs WHERE id=$1", log_id) == member
    assert await db.fetchval("SELECT id FROM users WHERE id=$1", member) == member
    assert await db.fetchval("SELECT id FROM notifications WHERE id=$1", notification) == notification


async def test_clean_removal_deletes_identity_and_cascades(account, removal, monkeypatch):
    db, owner, member, identity, notification = account
    calls = []
    monkeypatch.setattr(removal.keycloak_admin, "delete_user", calls.append)
    await removal.remove_team_account(db, user_id=member, tenant_id=owner, provider_only=True)
    assert calls == [str(identity)]
    assert await db.fetchval("SELECT id FROM users WHERE id=$1", member) is None
    assert await db.fetchval("SELECT id FROM notifications WHERE id=$1", notification) is None


async def test_keycloak_failure_preserves_database_and_cascades(account, removal, monkeypatch):
    db, owner, member, _, notification = account

    def unavailable(_):
        raise HTTPException(502, "simulated identity provider failure")

    monkeypatch.setattr(removal.keycloak_admin, "delete_user", unavailable)
    with pytest.raises(HTTPException) as exc:
        await removal.remove_team_account(db, user_id=member, tenant_id=owner)
    assert exc.value.status_code == 502
    assert await db.fetchval("SELECT id FROM users WHERE id=$1", member) == member
    assert await db.fetchval("SELECT id FROM notifications WHERE id=$1", notification) == notification


@pytest.mark.parametrize("target", ["other_tenant", "owner", "missing"])
async def test_out_of_scope_target_never_reaches_keycloak(account, removal, monkeypatch, target):
    db, owner, member, _, _ = account
    calls = []
    monkeypatch.setattr(removal.keycloak_admin, "delete_user", calls.append)
    with pytest.raises(HTTPException) as exc:
        await removal.remove_team_account(
            db, user_id=owner if target == "owner" else uuid4() if target == "missing" else member,
            tenant_id=uuid4() if target == "other_tenant" else owner,
        )
    assert exc.value.status_code == 404
    assert calls == []
    assert await db.fetchval("SELECT id FROM users WHERE id=$1", member) == member


async def test_business_member_cannot_use_provider_removal(account, removal, monkeypatch):
    db, owner, member, _, _ = account
    await db.execute("UPDATE users SET role='business' WHERE id=$1", member)
    calls = []
    monkeypatch.setattr(removal.keycloak_admin, "delete_user", calls.append)
    with pytest.raises(HTTPException) as exc:
        await removal.remove_team_account(db, user_id=member, tenant_id=owner, provider_only=True)
    assert exc.value.status_code == 404
    assert calls == []


async def test_other_foreign_key_returns_conflict_before_keycloak(account, removal, monkeypatch):
    db, owner, member, _, _ = account
    await db.execute("UPDATE users SET approved_by=$1 WHERE id=$2", member, owner)
    calls = []
    monkeypatch.setattr(removal.keycloak_admin, "delete_user", calls.append)
    with pytest.raises(HTTPException) as exc:
        await removal.remove_team_account(db, user_id=member, tenant_id=owner)
    assert exc.value.status_code == 409
    assert calls == []
    assert await db.fetchval("SELECT approved_by FROM users WHERE id=$1", owner) == member
