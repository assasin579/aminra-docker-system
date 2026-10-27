from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException


pytestmark = pytest.mark.asyncio


class FakeRecord(dict):
    """asyncpg.Record-like row supporting attribute access for compact assertions."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class FakeAuditDb:
    def __init__(self, visit_row: FakeRecord | None):
        self.visit_row = visit_row
        self.calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, sql: str, *args):
        self.calls.append((sql, args))
        assert "FROM audit_visits" in sql
        assert "provider_id" in sql
        assert "auditor_id" in sql
        assert "business_tenant" in sql
        return self.visit_row


def visit_row(*, provider_id=None, auditor_id=None, business_tenant=None) -> FakeRecord:
    return FakeRecord(
        id=uuid4(),
        provider_id=provider_id or uuid4(),
        auditor_id=auditor_id or uuid4(),
        business_tenant=business_tenant or uuid4(),
        status="in_progress",
    )


async def test_provider_owner_scope_allows_matching_canonical_provider(monkeypatch):
    from auth import audit_scope

    provider_id = uuid4()
    row = visit_row(provider_id=provider_id)

    async def fake_tenant(user, db):
        return provider_id

    async def fake_user(user, db):
        return uuid4()

    monkeypatch.setattr(audit_scope, "resolve_canonical_tenant_id", fake_tenant)
    monkeypatch.setattr(audit_scope, "resolve_canonical_user_id", fake_user)

    result = await audit_scope.assert_audit_visit_mutation_scope(
        row["id"], {"role": "provider", "is_owner": True}, FakeAuditDb(row)
    )

    assert result.visit == row
    assert result.scope == "provider_owner"
    assert result.canonical_tenant_id == provider_id


async def test_auditor_scope_allows_matching_canonical_auditor(monkeypatch):
    from auth import audit_scope

    auditor_id = uuid4()
    row = visit_row(auditor_id=auditor_id)

    async def fake_tenant(user, db):
        return uuid4()

    async def fake_user(user, db):
        return auditor_id

    monkeypatch.setattr(audit_scope, "resolve_canonical_tenant_id", fake_tenant)
    monkeypatch.setattr(audit_scope, "resolve_canonical_user_id", fake_user)

    result = await audit_scope.assert_audit_visit_mutation_scope(
        row["id"], {"role": "provider", "is_owner": False}, FakeAuditDb(row)
    )

    assert result.visit["id"] == row["id"]
    assert result.scope == "auditor"
    assert result.canonical_user_id == auditor_id


async def test_business_scope_requires_flag_and_matching_canonical_business_tenant(monkeypatch):
    from auth import audit_scope

    business_tenant = uuid4()
    row = visit_row(business_tenant=business_tenant)

    async def fake_tenant(user, db):
        return business_tenant

    async def fake_user(user, db):
        return uuid4()

    monkeypatch.setattr(audit_scope, "resolve_canonical_tenant_id", fake_tenant)
    monkeypatch.setattr(audit_scope, "resolve_canonical_user_id", fake_user)

    denied_db = FakeAuditDb(row)
    with pytest.raises(HTTPException) as denied:
        await audit_scope.assert_audit_visit_mutation_scope(row["id"], {"role": "business"}, denied_db)
    assert denied.value.status_code == 403

    result = await audit_scope.assert_audit_visit_mutation_scope(
        row["id"], {"role": "business"}, FakeAuditDb(row), allow_business=True
    )
    assert result.scope == "business"
    assert result.canonical_tenant_id == business_tenant


async def test_missing_visit_returns_404(monkeypatch):
    from auth import audit_scope

    async def fake_tenant(user, db):
        return uuid4()

    async def fake_user(user, db):
        return uuid4()

    monkeypatch.setattr(audit_scope, "resolve_canonical_tenant_id", fake_tenant)
    monkeypatch.setattr(audit_scope, "resolve_canonical_user_id", fake_user)

    with pytest.raises(HTTPException) as exc:
        await audit_scope.assert_audit_visit_mutation_scope(uuid4(), {"role": "provider", "is_owner": True}, FakeAuditDb(None))

    assert exc.value.status_code == 404


async def test_cross_provider_tenant_mismatch_returns_403(monkeypatch):
    from auth import audit_scope

    row = visit_row(provider_id=uuid4(), auditor_id=uuid4(), business_tenant=uuid4())

    async def fake_tenant(user, db):
        return uuid4()

    async def fake_user(user, db):
        return uuid4()

    monkeypatch.setattr(audit_scope, "resolve_canonical_tenant_id", fake_tenant)
    monkeypatch.setattr(audit_scope, "resolve_canonical_user_id", fake_user)

    with pytest.raises(HTTPException) as exc:
        await audit_scope.assert_audit_visit_mutation_scope(row["id"], {"role": "provider", "is_owner": True}, FakeAuditDb(row))

    assert exc.value.status_code == 403


async def test_cross_auditor_mismatch_returns_403(monkeypatch):
    from auth import audit_scope

    row = visit_row(auditor_id=uuid4())

    async def fake_tenant(user, db):
        return None

    async def fake_user(user, db):
        return uuid4()

    monkeypatch.setattr(audit_scope, "resolve_canonical_tenant_id", fake_tenant)
    monkeypatch.setattr(audit_scope, "resolve_canonical_user_id", fake_user)

    with pytest.raises(HTTPException) as exc:
        await audit_scope.assert_audit_visit_mutation_scope(row["id"], {"role": "auditor"}, FakeAuditDb(row))

    assert exc.value.status_code == 403


async def test_unresolved_canonical_identity_fails_closed(monkeypatch):
    from auth import audit_scope

    row = visit_row()

    async def fake_tenant(user, db):
        return None

    async def fake_user(user, db):
        return None

    monkeypatch.setattr(audit_scope, "resolve_canonical_tenant_id", fake_tenant)
    monkeypatch.setattr(audit_scope, "resolve_canonical_user_id", fake_user)

    with pytest.raises(HTTPException) as exc:
        await audit_scope.assert_audit_visit_mutation_scope(row["id"], {"role": "provider", "is_owner": True}, FakeAuditDb(row))

    assert exc.value.status_code in {403, 404}
