"""Canonical, actor-and-tenant bound scope for private auxiliary artifacts."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID
from fastapi import HTTPException
from auth.identity import resolve_canonical_user_id

@dataclass(frozen=True)
class PrivateScope:
    actor_id: UUID
    tenant_id: UUID

async def resolve_private_scope(user, db):
    actor_id = await resolve_canonical_user_id(user, db)
    if not actor_id:
        raise HTTPException(403, "Private resource scope unavailable")
    row = await db.fetchrow("SELECT id, tenant_id, status FROM users WHERE id=$1", actor_id)
    if not row or row['status'] != 'active' or not row['tenant_id']:
        raise HTTPException(403, "Private resource scope unavailable")
    return PrivateScope(UUID(str(row['id'])), UUID(str(row['tenant_id'])))

def review_path(root: Path, scope: PrivateScope, filename: str):
    # Hash the exact Unicode filename: no traversal, truncation or sanitization collision.
    return root / scope.tenant_id.hex / scope.actor_id.hex / (sha256(filename.encode('utf-8')).hexdigest()+'.json')
