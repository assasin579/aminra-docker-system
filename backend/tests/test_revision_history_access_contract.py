"""Route-level regression contracts for submission revision history access.

UUID values mirror asyncpg's UUID codec. These tests deliberately avoid a DB
connection so the authorization predicate itself remains fail-first and cheap.
"""
from uuid import uuid4

import pytest
from fastapi import HTTPException

from auth import submission_router
from services import submission_revisions


class SyntheticDB:
    def __init__(self, business_tenant, provider_id, auditor_id):
        self.row = {
            "business_tenant": business_tenant,
            "provider_id": provider_id,
            "auditor_id": auditor_id,
        }

    async def fetchrow(self, _query, *_args):
        return self.row


@pytest.fixture
def scoped_case(monkeypatch):
    business_tenant = uuid4()
    cb_owner_id = uuid4()
    assigned_auditor_id = uuid4()
    other_cb_id = uuid4()
    other_business_tenant = uuid4()
    submission_id = str(uuid4())
    db = SyntheticDB(business_tenant, cb_owner_id, assigned_auditor_id)

    async def resolve_tenant(user, _db):
        value = user.get("tenant_id")
        return value if hasattr(value, "hex") else __import__("uuid").UUID(str(value)) if value else None

    async def resolve_user(user, _db):
        value = user.get("sub")
        return value if hasattr(value, "hex") else __import__("uuid").UUID(str(value)) if value else None

    async def list_history(_db, _submission_id):
        return [{"round": 1, "feedback": "synthetic"}]

    monkeypatch.setattr(submission_router, "resolve_canonical_tenant_id", resolve_tenant)
    monkeypatch.setattr(submission_router, "resolve_canonical_user_id", resolve_user)
    monkeypatch.setattr(submission_revisions, "list_revision_history", list_history)
    return {
        "db": db,
        "submission_id": submission_id,
        "business_owner": {"role": "business", "is_owner": True, "sub": str(business_tenant), "tenant_id": business_tenant},
        "foreign_business": {"role": "business", "is_owner": True, "sub": str(other_business_tenant), "tenant_id": other_business_tenant},
        "cb_owner": {"role": "provider", "is_owner": True, "sub": str(cb_owner_id), "tenant_id": cb_owner_id},
        "other_cb_owner": {"role": "provider", "is_owner": True, "sub": str(other_cb_id), "tenant_id": other_cb_id},
        "assigned_auditor": {"role": "provider", "is_owner": False, "sub": str(assigned_auditor_id), "tenant_id": cb_owner_id},
        "unassigned_auditor": {"role": "provider", "is_owner": False, "sub": str(uuid4()), "tenant_id": cb_owner_id},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_key", ["business_owner", "cb_owner"])
async def test_history_is_visible_to_business_owner_and_cb_owner(scoped_case, actor_key):
    case = scoped_case
    result = await submission_router.get_revision_history(
        submission_id=case["submission_id"], user=case[actor_key], db=case["db"]
    )
    assert result["history"][0]["round"] == 1


@pytest.mark.asyncio
async def test_history_is_visible_to_assigned_auditor_only(scoped_case):
    case = scoped_case
    result = await submission_router.get_revision_history(
        submission_id=case["submission_id"], user=case["assigned_auditor"], db=case["db"]
    )
    assert result["history"][0]["round"] == 1

    for actor_key in ("foreign_business", "other_cb_owner", "unassigned_auditor"):
        with pytest.raises(HTTPException) as exc:
            await submission_router.get_revision_history(
                submission_id=case["submission_id"], user=case[actor_key], db=case["db"]
            )
        assert exc.value.status_code == 403
