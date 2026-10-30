"""Behavior contracts for owner-scoped rolling CB auditor performance metrics."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException


class RecordingDB:
    def __init__(self, *, owner_row=None, metrics_rows=None):
        self.calls = []
        self.owner_row = owner_row
        self.metrics_rows = metrics_rows or []

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.owner_row

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return self.metrics_rows


def _endpoint(router, path):
    return next((r.endpoint for r in router.routes if getattr(r, "path", None) == path), None)


def _owner_row(tenant_id):
    return {"id": uuid4(), "role": "provider", "status": "active", "is_owner": True, "tenant_id": tenant_id}


@pytest.mark.asyncio
async def test_cb_performance_denies_non_provider_and_platform_admin_before_db_lookup():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-performance")
    assert endpoint is not None
    db = RecordingDB(owner_row=_owner_row(uuid4()))
    denied_users = (
        {"role": "cb_admin", "is_owner": True},
        {"role": "business", "is_owner": True},
        {"role": "provider", "realm_roles": ["platform_admin"]},
        {"role": "provider", "realm_roles": ["auditor"]},
        {"role": "provider", "realm_roles": ["business"]},
    )
    for user in denied_users:
        with pytest.raises(HTTPException) as exc:
            await endpoint(user, db)
        assert exc.value.status_code == 403
    assert db.calls == []


@pytest.mark.asyncio
async def test_cb_performance_ignores_owner_claim_and_requires_canonical_persisted_owner():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-performance")
    assert endpoint is not None
    actor_id = uuid4()
    db = RecordingDB(owner_row={"id": actor_id, "role": "provider", "status": "active", "is_owner": False, "tenant_id": uuid4()})
    with pytest.raises(HTTPException) as exc:
        await endpoint({"role": "provider", "is_owner": True, "app_user_id": str(actor_id)}, db)
    assert exc.value.status_code == 403
    assert len(db.calls) == 1
    assert db.calls[0][0] == "fetchrow"
    assert "SELECT id, role, status, is_owner, tenant_id FROM users WHERE id = $1" in db.calls[0][1]
    assert all(not any(word in sql.upper() for word in ("UPDATE ", "INSERT ", "DELETE ")) for _, sql, _ in db.calls)


@pytest.mark.asyncio
async def test_cb_performance_denies_non_active_owner_even_when_persisted_owner_flag_is_true():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-performance")
    assert endpoint is not None
    actor_id = uuid4()
    db = RecordingDB(owner_row={"id": actor_id, "role": "provider", "status": "suspended", "is_owner": True, "tenant_id": uuid4()})
    with pytest.raises(HTTPException) as exc:
        await endpoint({"role": "provider", "app_user_id": str(actor_id)}, db)
    assert exc.value.status_code == 403
    assert [kind for kind, _, _ in db.calls] == ["fetchrow"]


@pytest.mark.asyncio
async def test_cb_performance_fails_closed_on_missing_row_or_bad_identity():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-performance")
    assert endpoint is not None
    for user, row in (
        ({"role": "provider", "app_user_id": str(uuid4())}, None),
        ({"role": "provider", "app_user_id": "not-a-uuid"}, None),
    ):
        db = RecordingDB(owner_row=row)
        with pytest.raises(HTTPException) as exc:
            await endpoint(user, db)
        assert exc.value.status_code == 403
        if user.get("app_user_id") == "not-a-uuid":
            assert db.calls == []


@pytest.mark.asyncio
async def test_provider_owner_with_null_tenant_uses_canonical_owner_id_without_writing():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-performance")
    assert endpoint is not None
    actor_id = uuid4()
    db = RecordingDB(owner_row={
        "id": actor_id, "role": "provider", "status": "active",
        "is_owner": True, "tenant_id": None,
    })
    result = await endpoint({"role": "provider", "app_user_id": str(actor_id)}, db)
    assert result["window_days"] == 90
    assert db.calls[1][2] == (actor_id,)
    assert all(kind in {"fetchrow", "fetch"} for kind, _, _ in db.calls)
    assert all(not any(word in sql.upper() for word in ("UPDATE ", "INSERT ", "DELETE ")) for _, sql, _ in db.calls)


@pytest.mark.asyncio
async def test_keycloak_owner_resolves_by_subject_not_email_or_claim_tenant():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-performance")
    assert endpoint is not None
    subject, tenant_id = uuid4(), uuid4()
    db = RecordingDB(owner_row={"id": uuid4(), "role": "provider", "status": "active", "is_owner": True, "tenant_id": tenant_id})
    result = await endpoint({"role": "provider", "realm_roles": ["cb_admin"], "_keycloak": True, "sub": str(subject), "email": "untrusted@example.invalid", "tenant_id": str(uuid4()), "is_owner": True}, db)
    assert result["window_days"] == 90
    assert db.calls[0][0] == "fetchrow"
    assert "WHERE keycloak_sub = $1" in db.calls[0][1]
    assert db.calls[0][2] == (subject,)
    assert db.calls[1][0] == "fetch"
    assert db.calls[1][2] == (tenant_id,)


@pytest.mark.asyncio
async def test_cb_performance_scopes_metrics_to_persisted_owner_tenant_and_acceptance_time():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-performance")
    assert endpoint is not None
    actor_id, tenant_id, auditor_id = uuid4(), uuid4(), uuid4()
    metrics = {
        "is_total": 0,
        "auditor_id": auditor_id,
        "auditor_name": "Auditor A",
        "current_completed": 3,
        "previous_completed": 2,
        "current_cycle_median_hours": 12.5,
        "current_cycle_p90_hours": 24.0,
        "previous_cycle_median_hours": 18.0,
        "previous_cycle_p90_hours": 36.0,
        "current_visit_turnaround_median_days": 2.0,
        "current_visit_turnaround_p90_days": 4.0,
        "previous_visit_turnaround_median_days": 3.0,
        "previous_visit_turnaround_p90_days": 6.0,
    }
    db = RecordingDB(owner_row=_owner_row(tenant_id), metrics_rows=[metrics])
    result = await endpoint({"role": "provider", "app_user_id": str(actor_id), "is_owner": None}, db)

    assert result["window_days"] == 90
    assert result["attribution"] == "report_accepted_at"
    assert result["auditors"][0]["auditor_id"] == str(auditor_id)
    assert result["auditors"][0]["completed"] == {"current_90d": 3, "previous_90d": 2}
    assert db.calls[0][2] == (actor_id,)
    sql, args = db.calls[1][1], db.calls[1][2]
    normalized = " ".join(sql.split()).lower()
    assert args == (tenant_id,)
    assert "av.provider_id = $1" in normalized
    assert "av.report_accepted_at" in normalized
    assert "interval '90 days'" in normalized and "interval '180 days'" in normalized
    assert "av.status = 'report_accepted'" in normalized
    assert "av.report_accepted_at <= now()" in normalized
    assert "report_accepted_at < now() - interval '90 days'" in normalized
    assert "report_accepted_at >= now() - interval '90 days'" in normalized
    assert "av.created_at" in normalized and "av.scheduled_date" in normalized


@pytest.mark.asyncio
async def test_cb_performance_does_not_invent_auditors_or_percentiles_for_empty_history():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-performance")
    assert endpoint is not None
    tenant_id = uuid4()
    db = RecordingDB(owner_row=_owner_row(tenant_id))
    result = await endpoint({"role": "provider", "app_user_id": str(uuid4())}, db)
    assert result["auditors"] == []
    assert result["total"] == {
        "completed": {"current_90d": 0, "previous_90d": 0},
        "cycle_time_hours": {"current_median": None, "current_p90": None, "previous_median": None, "previous_p90": None},
        "scheduled_to_acceptance_days": {"current_median": None, "current_p90": None, "previous_median": None, "previous_p90": None},
    }
    assert [kind for kind, _, _ in db.calls] == ["fetchrow", "fetch"]


class ProviderStatsDB:
    def __init__(self, canonical_row):
        self.canonical_row = canonical_row
        self.calls = []

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        if "SELECT id, role, status, is_owner, tenant_id FROM users" in sql:
            return self.canonical_row
        if "FROM halal_certificates" in sql:
            return {"total": 0, "active": 0, "expiring_soon": 0, "inactive": 0}
        if "FROM audit_visits" in sql:
            return {"total": 0, "completed": 0, "avg_compliance": None}
        if "FROM submissions" in sql:
            return {"pending": 0, "reviewing": 0, "approved": 0, "returned": 0, "total": 0, "overdue": 0, "avg_hours": None}
        return {"pending": 0, "reviewing": 0, "approved": 0, "returned": 0, "total": 0, "overdue": 0}

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        return None

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return []


@pytest.mark.asyncio
async def test_cb_stats_requires_persisted_active_owner_and_uses_canonical_tenant():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-stats")
    assert endpoint is not None
    actor_id, tenant_id = uuid4(), uuid4()

    # Untrusted role/owner/tenant claims cannot grant access; only canonical DB state counts.
    denied_db = ProviderStatsDB({
        "id": actor_id, "role": "provider", "status": "active",
        "is_owner": False, "tenant_id": tenant_id,
    })
    with pytest.raises(HTTPException) as exc:
        await endpoint({
            "role": "provider", "realm_roles": ["cb_admin"], "app_user_id": str(actor_id),
            "is_owner": True, "tenant_id": str(tenant_id),
        }, denied_db)
    assert exc.value.status_code == 403
    assert len(denied_db.calls) == 1
    assert "FROM users" in denied_db.calls[0][1]
    assert all(not any(word in sql.upper() for word in ("UPDATE ", "INSERT ", "DELETE ")) for _, sql, _ in denied_db.calls)

    owner_db = ProviderStatsDB({
        "id": actor_id, "role": "provider", "status": "active",
        "is_owner": True, "tenant_id": tenant_id,
    })
    await endpoint({
        "role": "provider", "realm_roles": ["cb_admin"], "app_user_id": str(actor_id),
        "is_owner": False, "tenant_id": str(uuid4()),
    }, owner_db)
    scoped_queries = [(sql, args) for _, sql, args in owner_db.calls[1:]]
    assert scoped_queries
    assert all(args == (tenant_id,) for _, args in scoped_queries)
    assert all(not any(word in sql.upper() for word in ("UPDATE ", "INSERT ", "DELETE ")) for _, sql, _ in owner_db.calls)


@pytest.mark.asyncio
async def test_cb_stats_certificate_expiry_remains_60_days_separate_from_90d_performance():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-stats")
    actor_id, tenant_id = uuid4(), uuid4()
    db = ProviderStatsDB({
        "id": actor_id, "role": "provider", "status": "active",
        "is_owner": True, "tenant_id": tenant_id,
    })
    await endpoint({"role": "provider", "app_user_id": str(actor_id)}, db)
    expiry_queries = [
        sql.lower() for _, sql, _ in db.calls
        if "halal_certificates" in sql.lower() and "expiry_date" in sql.lower()
    ]
    assert len(expiry_queries) >= 2
    assert all("interval '60 days'" in sql for sql in expiry_queries)
    assert all("interval '90 days'" not in sql for sql in expiry_queries)


@pytest.mark.asyncio
async def test_cb_stats_denies_business_auditor_and_platform_admin_before_metrics_queries():
    """Owner aggregates fail closed for non-owner capabilities on this endpoint."""
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-stats")
    assert endpoint is not None
    canonical_owner = {
        "id": uuid4(), "role": "provider", "status": "active",
        "is_owner": True, "tenant_id": uuid4(),
    }

    for user, expected_lookup_count in (
        ({"role": "business", "app_user_id": str(canonical_owner["id"])}, 0),
        ({"role": "provider", "realm_roles": ["auditor"], "app_user_id": str(canonical_owner["id"])}, 1),
        ({"role": "provider", "realm_roles": ["platform_admin"], "app_user_id": str(canonical_owner["id"])}, 0),
    ):
        db = ProviderStatsDB(canonical_owner)
        with pytest.raises(HTTPException) as exc:
            await endpoint(user, db)
        assert exc.value.status_code == 403
        assert len(db.calls) == expected_lookup_count
        assert all(kind == "fetchrow" and "FROM users" in sql for kind, sql, _ in db.calls)


@pytest.mark.asyncio
async def test_cb_stats_same_tenant_non_owner_cannot_use_owner_aggregate_capability():
    """A provider auditor in the right tenant is still not an organization owner."""
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/cb-stats")
    assert endpoint is not None
    actor_id, tenant_id = uuid4(), uuid4()
    db = ProviderStatsDB({
        "id": actor_id, "role": "provider", "status": "active",
        "is_owner": False, "tenant_id": tenant_id,
    })
    with pytest.raises(HTTPException) as exc:
        await endpoint({
            "role": "provider", "realm_roles": ["cb_admin"],
            "app_user_id": str(actor_id), "tenant_id": str(tenant_id),
        }, db)
    assert exc.value.status_code == 403
    assert len(db.calls) == 1
    assert "FROM users" in db.calls[0][1]
    assert all(not any(word in sql.upper() for word in ("UPDATE ", "INSERT ", "DELETE ")) for _, sql, _ in db.calls)


@pytest.mark.asyncio
async def test_provider_queue_stats_use_canonical_owner_or_auditor_scope_and_deny_platform_admin():
    from auth import submission_router

    endpoint = _endpoint(submission_router.router, "/stats")
    assert endpoint is not None

    owner_id, tenant_id = uuid4(), uuid4()
    owner_db = ProviderStatsDB({
        "id": owner_id, "role": "provider", "status": "active",
        "is_owner": True, "tenant_id": tenant_id,
    })
    await endpoint({
        "role": "provider", "realm_roles": ["cb_admin"], "app_user_id": str(owner_id),
        "is_owner": False, "tenant_id": str(uuid4()),
    }, owner_db)
    owner_query = next(sql for kind, sql, _ in owner_db.calls if kind == "fetchrow" and "FROM submissions s" in sql)
    assert "s.provider_id = $1" in owner_query
    assert next(args for kind, sql, args in owner_db.calls if kind == "fetchrow" and "FROM submissions s" in sql) == (tenant_id,)

    auditor_id, auditor_tenant = uuid4(), uuid4()
    auditor_db = ProviderStatsDB({
        "id": auditor_id, "role": "provider", "status": "active",
        "is_owner": False, "tenant_id": auditor_tenant,
    })
    await endpoint({
        "role": "provider", "realm_roles": ["auditor"], "app_user_id": str(auditor_id),
        "is_owner": True, "tenant_id": str(uuid4()),
    }, auditor_db)
    auditor_query = next(sql for kind, sql, _ in auditor_db.calls if kind == "fetchrow" and "FROM submissions s" in sql)
    assert "s.auditor_id = $1" in auditor_query
    assert next(args for kind, sql, args in auditor_db.calls if kind == "fetchrow" and "FROM submissions s" in sql) == (auditor_id,)

    admin_db = ProviderStatsDB({
        "id": uuid4(), "role": "provider", "status": "active",
        "is_owner": True, "tenant_id": tenant_id,
    })
    with pytest.raises(HTTPException) as exc:
        await endpoint({"role": "provider", "realm_roles": ["platform_admin"], "app_user_id": str(uuid4())}, admin_db)
    assert exc.value.status_code == 403
    assert admin_db.calls == []

    business_db = ProviderStatsDB({
        "id": uuid4(), "role": "business", "status": "active",
        "is_owner": True, "tenant_id": uuid4(),
    })
    with pytest.raises(HTTPException) as exc:
        await endpoint({"role": "business", "app_user_id": str(uuid4())}, business_db)
    assert exc.value.status_code == 403
    assert business_db.calls == []
