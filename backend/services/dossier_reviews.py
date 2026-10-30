"""Immutable CB review evidence bound to requirements, round and document version."""
from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException


async def record_bound_submission_review(db, *, submission, user: dict) -> None:
    """Must run inside the approval transaction; audit failure fails the approval."""
    if submission.get('requirements_binding_status') != 'bound' or not submission.get('requirements_version_id'):
        return  # Historical unbound submissions never acquire an invented binding.
    from auth.submission_router import _resolve_cb_provider_actor
    actor = await _resolve_cb_provider_actor(user, db)
    if not actor or str(actor['tenant_id']) != str(submission['provider_id']):
        raise HTTPException(403, 'CB reviewer scope required')
    if not actor['is_owner'] and str(actor['actor_id']) != str(submission.get('auditor_id')):
        raise HTTPException(403, 'Assigned auditor required')
    ids = list(submission.get('document_ids') or [])
    rows = await db.fetch('SELECT id, version_number FROM documents WHERE tenant_id=$1 AND id=ANY($2::uuid[])',submission['business_tenant'],ids)
    if not ids or len(rows) != len(set(ids)):
        raise HTTPException(409, 'Submitted evidence changed; review the dossier again')
    metadata = {
        'provider_id':str(submission['provider_id']),
        'requirements_version_id':str(submission['requirements_version_id']),
        'submitted_round':int(submission.get('revision_round') or 0)+1,
        'document_versions':{str(row['id']):row['version_number'] for row in rows},
    }
    await db.execute(
        "INSERT INTO audit_logs(user_id,user_email,user_role,tenant_id,action,entity_type,entity_id,metadata) "
        "VALUES($1,$2,'provider',$3,'submission.documents_reviewed','submission',$4,$5::jsonb)",
        actor['actor_id'],user.get('email'),actor['tenant_id'],submission['id'],json.dumps(metadata),
    )


async def reviewed_document_versions(db, *, submission, requirements_version_id) -> dict[str, Any]:
    if not submission:
        return {}
    row = await db.fetchrow(
        """SELECT metadata FROM audit_logs
           WHERE entity_type='submission' AND entity_id=$1
             AND action='submission.documents_reviewed' AND user_role='provider'
             AND metadata->>'provider_id'=$2
             AND metadata->>'requirements_version_id'=$3
             AND metadata->>'submitted_round'=$4
           ORDER BY created_at DESC, id DESC LIMIT 1""",
        submission['id'],str(submission['provider_id']),str(requirements_version_id),
        str(int(submission.get('revision_round') or 0)+1),
    )
    metadata = row['metadata'] if row else {}
    if isinstance(metadata,str):
        try:metadata=json.loads(metadata)
        except (ValueError,TypeError):return {}
    versions=metadata.get('document_versions') if isinstance(metadata,dict) else None
    return versions if isinstance(versions,dict) else {}
