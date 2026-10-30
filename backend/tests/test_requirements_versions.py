from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.requirements_versions import canonicalize_requirement_slots, publish_requirements_version


def test_canonical_snapshot_is_order_independent_and_normalizes_unicode():
    a = [{"doc_type": "étiquette", "required": True, "display_order": 1}, {"doc_type": "policy", "required": False, "display_order": 0}]
    b = [{"doc_type": "policy", "required": False, "display_order": 0}, {"doc_type": "e\u0301tiquette", "required": True, "display_order": 1}]
    slots_a, hash_a = canonicalize_requirement_slots(a)
    slots_b, hash_b = canonicalize_requirement_slots(b)
    assert slots_a == slots_b
    assert hash_a == hash_b


def test_canonical_snapshot_hash_tracks_requirement_semantics():
    _, required_hash = canonicalize_requirement_slots([{"doc_type": "policy", "required": True, "display_order": 1}])
    _, optional_hash = canonicalize_requirement_slots([{"doc_type": "policy", "required": False, "display_order": 1}])
    _, reordered_hash = canonicalize_requirement_slots([{"doc_type": "policy", "required": True, "display_order": 2}])
    assert len({required_hash, optional_hash, reordered_hash}) == 3


def test_canonical_snapshot_rejects_duplicate_or_blank_slots():
    with pytest.raises(HTTPException) as exc:
        canonicalize_requirement_slots([
            {"doc_type": "policy", "required": True, "display_order": 1},
            {"doc_type": " policy ", "required": False, "display_order": 2},
        ])
    assert exc.value.status_code == 409


class PublishDB:
    def __init__(self, standard_id, slots):
        self.standard_id = standard_id
        self.slots = list(slots)
        self.versions = []
        self.version_slots = {}
        self.current = None
        self.audit = []
        self.fail_audit = False
        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def transaction(self):
        async with self.lock:
            before = deepcopy((self.versions, self.version_slots, self.current, self.audit))
            try:
                yield
            except Exception:
                self.versions, self.version_slots, self.current, self.audit = before
                raise

    async def fetchrow(self, query, *args):
        if "SELECT id FROM standard_types" in query:
            return {"id": self.standard_id} if args[0] == self.standard_id else None
        if "JOIN standard_requirement_versions" in query:
            if self.current is None:
                return None
            return next(v for v in self.versions if v["id"] == self.current)
        if "INSERT INTO standard_requirement_versions" in query:
            version = {"id": uuid4(), "standard_type_id": args[0], "version_number": args[1], "state": "draft", "content_sha256": args[2]}
            self.versions.append(version)
            return {"id": version["id"]}
        raise AssertionError(query)

    async def fetch(self, query, *args):
        assert "FROM standard_doc_types" in query
        return list(self.slots)

    async def fetchval(self, query, *args):
        return max((v["version_number"] for v in self.versions), default=0) + 1

    async def execute(self, query, *args):
        if "INSERT INTO standard_requirement_version_slots" in query:
            version_id, _, doc_type, required, order = args
            self.version_slots.setdefault(version_id, []).append({"doc_type": doc_type, "required": required, "display_order": order})
        elif "UPDATE standard_requirement_versions" in query:
            version = next(v for v in self.versions if v["id"] == args[0])
            version.update(state="published", published_by=args[1])
        elif "INSERT INTO standard_requirement_current_versions" in query:
            self.current = args[1]
        elif "INSERT INTO audit_logs" in query:
            if self.fail_audit:
                raise RuntimeError("audit insert failed")
            self.audit.append(args)
        else:
            raise AssertionError(query)


PLATFORM_ADMIN = {"_keycloak": True, "realm_roles": ["platform_admin"], "role": "provider", "sub": "kc-admin", "email": "admin@example.test"}


async def test_publish_is_idempotent_concurrent_and_preserves_prior_version_snapshot():
    standard_id, actor_id = uuid4(), uuid4()
    db = PublishDB(standard_id, [
        {"doc_type": "policy", "required": True, "display_order": 1},
        {"doc_type": "records", "required": False, "display_order": 2},
    ])
    first, second = await asyncio.gather(*[
        publish_requirements_version(db, standard_type_id=standard_id, actor=PLATFORM_ADMIN, actor_id=actor_id)
        for _ in range(2)
    ])
    assert first["requirements_version_id"] == second["requirements_version_id"]
    assert first["version_number"] == second["version_number"] == 1
    assert len(db.versions) == 1
    first_id = db.current
    assert db.version_slots[first_id][0]["doc_type"] == "policy"
    db.slots = [{"doc_type": "policy", "required": False, "display_order": 1}]
    third = await publish_requirements_version(db, standard_type_id=standard_id, actor=PLATFORM_ADMIN, actor_id=actor_id)
    assert third["version_number"] == 2
    assert db.version_slots[first_id][0]["required"] is True
    assert db.current != first_id
    retry = await publish_requirements_version(db, standard_type_id=standard_id, actor=PLATFORM_ADMIN, actor_id=actor_id)
    assert retry["requirements_version_id"] == third["requirements_version_id"]
    assert retry["unchanged"] is True
    assert len(db.versions) == 2


async def test_publish_failure_rolls_back_version_slots_pointer_and_audit():
    standard_id, actor_id = uuid4(), uuid4()
    db = PublishDB(standard_id, [{"doc_type": "policy", "required": True, "display_order": 1}])
    db.fail_audit = True
    with pytest.raises(RuntimeError, match="audit insert failed"):
        await publish_requirements_version(db, standard_type_id=standard_id, actor=PLATFORM_ADMIN, actor_id=actor_id)
    assert db.versions == []
    assert db.version_slots == {}
    assert db.current is None
    assert db.audit == []


class NoDB:
    @asynccontextmanager
    async def transaction(self):
        raise AssertionError("authorization must fail before DB access")
        yield


@pytest.mark.parametrize("actor", [
    {"_keycloak": True, "realm_roles": ["provider"], "role": "provider", "sub": "kc-1"},
    {"_keycloak": True, "realm_roles": ["cb_admin"], "role": "provider", "sub": "kc-2", "is_owner": True},
    {"_keycloak": True, "realm_roles": ["auditor"], "role": "provider", "sub": "kc-3"},
    {"_keycloak": True, "realm_roles": ["business"], "role": "business", "sub": "kc-4"},
    {"_keycloak": True, "realm_roles": [], "role": "platform_admin", "sub": "kc-5"},
    {"_keycloak": False, "realm_roles": ["platform_admin"], "role": "platform_admin", "sub": "kc-6"},
    {"role": "platform_admin"},
    {},
])
async def test_publish_rejects_non_platform_admin_or_unverified_identity(actor):
    with pytest.raises(HTTPException) as exc:
        await publish_requirements_version(NoDB(), standard_type_id=uuid4(), actor=actor, actor_id=uuid4())
    assert exc.value.status_code == 403


async def test_publish_requires_canonical_app_user_id_even_with_verified_capability():
    actor = {"_keycloak": True, "realm_roles": ["platform_admin"], "role": "provider", "sub": "kc-admin"}
    with pytest.raises(HTTPException) as exc:
        await publish_requirements_version(NoDB(), standard_type_id=uuid4(), actor=actor, actor_id=None)
    assert exc.value.status_code == 403
