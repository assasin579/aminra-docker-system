"""Disposable-PostgreSQL acceptance for J1/J2 submission history.

Runs only when an explicit per-run DATABASE_URL is supplied. Fixtures are
created per test and use reserved synthetic domains/labels only. The required
non-superuser role assertion prevents accidental runs as migration owner.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from auth import document_router, submission_router
from services.submission_revisions import request_revision
from services.dossier_attachments import attach_document_reference, validate_dossier_slot


def synthetic_request(*, headers: dict[str, str] | None = None) -> Request:
    request_headers = {"user-agent": "aminra-j1j2-disposable", **(headers or {})}
    return Request({
        "type": "http", "method": "POST", "path": "/synthetic-j1-j2",
        "scheme": "http", "query_string": b"", "server": ("synthetic.invalid", 80),
        "client": ("127.0.0.1", 1234),
        "headers": [(key.lower().encode(), value.encode()) for key, value in request_headers.items()],
    })


@pytest.fixture
async def db():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set; disposable PostgreSQL acceptance only")
    conn = await asyncpg.connect(url)
    try:
        role = await conn.fetchrow(
            """SELECT current_user AS role, r.rolsuper, r.rolbypassrls
               FROM pg_roles r WHERE r.rolname = current_user"""
        )
        expected = os.getenv("J1J2_APP_ROLE", "aminra_j1j2_app")
        assert role["role"] == expected, "test must connect as the dedicated application role"
        assert role["rolsuper"] is False
        assert role["rolbypassrls"] is False
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def case(db):
    ids = {key: uuid4() for key in (
        "business_a", "business_b", "cb_p", "cb_p_tenant", "cb_q", "assigned", "unassigned",
        "standard", "requirements", "dossier", "submission",
    )}

    async def add_user(key: str, role: str, *, owner: bool, tenant: str | None = None):
        user_id = ids[key]
        email = f"{key}-{user_id.hex[:8]}@example.invalid"
        await db.execute(
            """INSERT INTO users
               (id, email, role, company_name, status, tenant_id, is_owner)
               VALUES ($1, $2, $3, $4, 'active', $5, $6)""",
            user_id, email, role, f"Synthetic {key}", ids[tenant] if tenant else user_id, owner,
        )
        return {
            "id": user_id, "sub": str(user_id), "email": email,
            "role": role, "is_owner": owner,
            "tenant_id": str(ids[tenant] if tenant else user_id),
        }

    business_a = await add_user("business_a", "business", owner=True)
    business_b = await add_user("business_b", "business", owner=True)
    cb_p = await add_user("cb_p", "provider", owner=True, tenant="cb_p_tenant")
    await add_user("cb_p_tenant", "provider", owner=True)
    cb_q = await add_user("cb_q", "provider", owner=True)
    assigned = await add_user("assigned", "provider", owner=False, tenant="cb_p_tenant")
    unassigned = await add_user("unassigned", "provider", owner=False, tenant="cb_p_tenant")

    await db.execute(
        "INSERT INTO standard_types (id, code, name_vi) VALUES ($1, $2, $3)",
        ids["standard"], f"synthetic-{ids['standard'].hex[:12]}", "Synthetic J1/J2 profile",
    )
    requirements_hash = hashlib.sha256(b"synthetic-requirements-v1").hexdigest()
    await db.execute(
        """INSERT INTO standard_requirement_versions
           (id, standard_type_id, version_number, state, content_sha256, created_by)
           VALUES ($1, $2, 1, 'draft', $3, $4)""",
        ids["requirements"], ids["standard"], requirements_hash, cb_p["id"],
    )
    doc_types = ["permit", "manual", "supporting", "legacy-extra", "certificate", "policy"]
    for order, doc_type in enumerate(doc_types):
        await db.execute(
            """INSERT INTO standard_requirement_version_slots
               (requirements_version_id, standard_type_id, doc_type, required, display_order)
               VALUES ($1, $2, $3, $4, $5)""",
            ids["requirements"], ids["standard"], doc_type, doc_type != "legacy-extra", order,
        )
    await db.execute(
        """UPDATE standard_requirement_versions
           SET state='published', published_by=$1, published_at=now() WHERE id=$2""",
        cb_p["id"], ids["requirements"],
    )
    await db.execute(
        """INSERT INTO dossiers
           (id, tenant_id, standard_type_id, title, status, created_by,
            requirements_version_id, requirements_binding_status)
           VALUES ($1, $2, $3, 'Synthetic J1/J2 dossier', 'draft', $4, $5, 'bound')""",
        ids["dossier"], ids["business_a"], ids["standard"], ids["business_a"], ids["requirements"],
    )

    docs: dict[str, dict] = {}

    async def add_doc(key: str, doc_type: str, version: int = 1, parent: str | None = None):
        doc_id = uuid4()
        path = f"synthetic://{ids['submission']}/{key}/v{version}"
        size = 100 + len(key) + version
        await db.execute(
            """INSERT INTO documents
               (id, filename, original_filename, file_path, file_size, mime_type,
                user_id, tenant_id, doc_type, version_number, version_parent_id,
                dossier_id, status)
               VALUES ($1, $2, $2, $3, $4, 'application/pdf', $5, $6, $7, $8, $9, $10, 'uploaded')""",
            doc_id, f"{key}-v{version}.pdf", path, size, ids["business_a"],
            ids["business_a"], doc_type, version, docs[parent]["id"] if parent else None,
            ids["dossier"],
        )
        docs[key] = {"id": doc_id, "doc_type": doc_type, "version_number": version, "file_path": path, "file_size": size}
        return doc_id

    old_permit = await add_doc("permit-v1", "permit")
    old_manual = await add_doc("manual-v1", "manual")
    old_support = await add_doc("support-v1", "supporting")
    old_extra = await add_doc("extra-v1", "legacy-extra")
    new_permit = await add_doc("permit-v2", "permit", 2, "permit-v1")
    new_support = await add_doc("support-v2", "supporting", 2, "support-v1")
    new_certificate = await add_doc("certificate-v1", "certificate")
    new_manual = await add_doc("manual-v2", "manual", 2, "manual-v1")
    wrong_doc = await add_doc("wrong-v1", "wrong-type")
    policy_doc = await add_doc("policy-v1", "policy")

    initial_docs = [old_permit, old_manual, old_support, old_extra]
    await db.execute(
        """INSERT INTO submissions
           (id, business_tenant, provider_id, auditor_id, document_ids, status,
            company_name, revision_round, requirements_version_id, requirements_binding_status)
           VALUES ($1, $2, $3, $4, $5::uuid[], 'reviewing', 'Synthetic Business A', 0, $6, 'bound')""",
        ids["submission"], ids["business_a"], ids["cb_p_tenant"], assigned["id"],
        initial_docs, ids["requirements"],
    )


    return {
        "ids": ids,
        "users": {
            "business_a": business_a, "business_b": business_b, "cb_p": cb_p,
            "cb_q": cb_q, "assigned": assigned, "unassigned": unassigned,
        },
        "docs": docs,
        "initial_docs": initial_docs,
        "round1_docs": [new_permit, old_manual, new_support, new_certificate],
        "round2_docs": [new_permit, new_manual, new_support, new_certificate],
        "wrong_docs": [old_permit, wrong_doc],
        "policy_doc": policy_doc,
    }


@pytest.mark.asyncio
async def test_submit_routes_owner_selected_cb_to_canonical_org_tenant(db, case, monkeypatch):
    async def no_notify(*_args, **_kwargs):
        return None

    async def no_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(submission_router, "notify", no_notify)
    monkeypatch.setattr(submission_router, "log_audit", no_audit)
    business = case["users"]["business_a"]
    cb_owner = case["users"]["cb_p"]
    result = await submission_router.submit_documents(
        req=submission_router.SubmitRequest(
            provider_id=str(cb_owner["id"]),
            document_ids=[str(case["initial_docs"][0])],
            notes="synthetic recipient-routing regression",
        ),
        request=synthetic_request(), owner=business, db=db,
    )
    row = await db.fetchrow(
        "SELECT provider_id FROM submissions WHERE id=$1", UUID(result["submission_id"]),
    )
    assert str(row["provider_id"]) == str(case["ids"]["cb_p_tenant"])
    received = await submission_router.received_submissions(user=cb_owner, db=db)
    assert any(item["id"] == result["submission_id"] for item in received["submissions"])
    unrelated = await submission_router.received_submissions(user=case["users"]["cb_q"], db=db)
    assert all(item["id"] != result["submission_id"] for item in unrelated["submissions"])


async def _request_revision(monkeypatch, db, case, feedback: str = "Synthetic round feedback"):
    async def no_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(submission_router, "notify", no_notify)
    return await submission_router.provider_request_revision(
        submission_id=str(case["ids"]["submission"]),
        req=submission_router.RequestRevisionIn(
            feedback=feedback,
            document_feedback=[submission_router.DocumentFeedbackIn(
                document_id=str(case["initial_docs"][0]),
                issue="Synthetic missing field", severity="major", suggestion="Provide exact version",
            )],
        ),
        request=synthetic_request(), user=case["users"]["assigned"], db=db,
    )


@pytest.mark.asyncio
async def test_replacement_preserves_open_revision_until_explicit_resubmit_retry(db, case, monkeypatch):
    await _request_revision(monkeypatch, db, case, "Replace the policy evidence")
    old_doc = case["initial_docs"][0]
    new_doc = case["docs"]["permit-v2"]["id"]
    business = case["users"]["business_a"]
    await submission_router.replace_submission_document(
        submission_id=str(case["ids"]["submission"]),
        request={"old_doc_id": str(old_doc), "new_doc_id": str(new_doc)},
        user=business, db=db,
    )

    after_replace = await db.fetchrow(
        "SELECT status, revision_round, document_ids FROM submissions WHERE id=$1",
        case["ids"]["submission"],
    )
    request_row = await db.fetchrow(
        """SELECT resolved_at, submitted_round, submitted_document_ids
             FROM submission_revision_requests WHERE submission_id=$1 AND round=1""",
        case["ids"]["submission"],
    )
    assert after_replace["status"] == "revision_required"
    assert after_replace["revision_round"] == 1
    assert new_doc in after_replace["document_ids"]
    assert request_row["resolved_at"] is None
    assert request_row["submitted_round"] == 1
    assert request_row["submitted_document_ids"] == case["initial_docs"]

    notifications = []
    audits = []
    async def capture_notify(*args, **kwargs):
        notifications.append((args, kwargs))
    async def capture_audit(*args, **kwargs):
        audits.append((args, kwargs))
    monkeypatch.setattr(submission_router, "notify", capture_notify)
    monkeypatch.setattr(submission_router, "log_audit", capture_audit)
    retry_request = synthetic_request(headers={"Idempotency-Key": "explicit-resubmit-after-replacement"})
    payload = submission_router.ResubmitIn(business_notes="Policy evidence replaced")
    first = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=retry_request, owner=business, db=db,
    )
    second = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=retry_request, owner=business, db=db,
    )
    assert second == first
    assert len(notifications) == 1
    assert len(audits) == 1

    final = await db.fetchrow(
        "SELECT status, revision_round, document_ids FROM submissions WHERE id=$1",
        case["ids"]["submission"],
    )
    resolved = await db.fetchrow(
        """SELECT resolved_at, submitted_round, submitted_document_ids
             FROM submission_revision_requests WHERE submission_id=$1 AND round=1""",
        case["ids"]["submission"],
    )
    assert final["status"] == "reviewing"
    assert final["revision_round"] == 1
    assert new_doc in final["document_ids"]
    assert resolved["resolved_at"] is not None
    assert resolved["submitted_round"] == 1
    assert resolved["submitted_document_ids"] == case["initial_docs"]


@pytest.mark.asyncio
async def test_revision_history_scope_snapshot_and_uuid_values(db, case, monkeypatch):
    created = await _request_revision(monkeypatch, db, case)
    assert created["round"] == 1

    # Deliberately change only the mutable current pointer after recording the
    # round. History must remain sourced from submitted_document_ids.
    await db.execute(
        "UPDATE submissions SET document_ids=$1::uuid[] WHERE id=$2",
        [case["docs"]["certificate-v1"]["id"]], case["ids"]["submission"],
    )

    for actor_key in ("business_a", "cb_p", "assigned"):
        result = await submission_router.get_revision_history(
            str(case["ids"]["submission"]), user=case["users"][actor_key], db=db,
        )
        assert len(result["history"]) == 1
        assert result["history"][0]["round"] == 1
        assert result["history"][0]["requirements_version_id"] == str(case["ids"]["requirements"])
        assert result["history"][0]["submitted_round"] == 1
        assert result["history"][0]["submitted_document_ids"] == [str(x) for x in case["initial_docs"]]

    denied = ["business_b", "cb_q", "unassigned"]
    for actor_key in denied:
        with pytest.raises(HTTPException) as exc:
            await submission_router.get_revision_history(
                str(case["ids"]["submission"]), user=case["users"][actor_key], db=db,
            )
        assert exc.value.status_code == 403

    missing_identity = {"role": "provider", "is_owner": False, "tenant_id": None}
    with pytest.raises(HTTPException) as exc:
        await submission_router.get_revision_history(
            str(case["ids"]["submission"]), user=missing_identity, db=db,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_resubmit_rejects_document_type_outside_pinned_requirements(db, case, monkeypatch):
    await _request_revision(monkeypatch, db, case)
    owner = case["users"]["business_a"]
    with pytest.raises(HTTPException) as exc:
        await submission_router.business_resubmit(
            submission_id=str(case["ids"]["submission"]),
            req=submission_router.ResubmitIn(new_document_ids=[str(x) for x in case["wrong_docs"]], business_notes="Synthetic"),
            request=synthetic_request(), owner=owner, db=db,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "replacement document type is not mapped by the bound requirements version"
    row = await db.fetchrow(
        "SELECT status, revision_round, document_ids FROM submissions WHERE id=$1",
        case["ids"]["submission"],
    )
    assert row["status"] == "revision_required"
    assert row["revision_round"] == 1
    assert row["document_ids"] == case["initial_docs"]
    pending = await db.fetchrow(
        "SELECT id, round, resolved_at, business_response, requirements_version_id, submitted_document_ids, submitted_round\n         FROM submission_revision_requests WHERE submission_id=$1 AND round=1",
        case["ids"]["submission"],
    )
    assert pending is not None
    assert pending["resolved_at"] is None
    assert pending["business_response"] is None
    assert pending["requirements_version_id"] == case["ids"]["requirements"]
    assert pending["submitted_document_ids"] == case["initial_docs"]
    assert pending["submitted_round"] == 1
    request_count = await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1",
        case["ids"]["submission"],
    )
    assert request_count == 1

    async def no_notify(*_args, **_kwargs):
        return None
    monkeypatch.setattr(submission_router, "notify", no_notify)
    accepted = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]),
        req=submission_router.ResubmitIn(
            new_document_ids=[str(x) for x in case["round1_docs"]],
            business_notes="Valid pinned document types",
        ),
        request=synthetic_request(), owner=owner, db=db,
    )
    assert accepted["round_resolved"] == 1
    after = await db.fetchrow(
        "SELECT status, revision_round, document_ids FROM submissions WHERE id=$1",
        case["ids"]["submission"],
    )
    assert after["status"] == "reviewing"
    assert after["revision_round"] == 1
    assert after["document_ids"] == case["round1_docs"]
    resolved = await db.fetchrow(
        "SELECT resolved_at, business_response FROM submission_revision_requests WHERE submission_id=$1 AND round=1",
        case["ids"]["submission"],
    )
    assert resolved["resolved_at"] is not None
    assert resolved["business_response"] == "Valid pinned document types"


@pytest.mark.asyncio
async def test_j2_round_resubmit_diff_and_old_snapshot_immutability(db, case, monkeypatch):
    await _request_revision(monkeypatch, db, case, "Round 1 synthetic feedback")
    old_row = await db.fetchrow(
        """SELECT id, round, requester_id, requester_name, feedback, document_feedback,
                  requirements_version_id, submitted_document_ids, submitted_round, requested_at
           FROM submission_revision_requests WHERE submission_id=$1 AND round=1""",
        case["ids"]["submission"],
    )
    old_hash = hashlib.sha256(json.dumps(dict(old_row), default=str, sort_keys=True).encode()).hexdigest()
    old_file_meta = await db.fetch(
        "SELECT id, file_path, file_size, version_number FROM documents WHERE id=ANY($1::uuid[]) ORDER BY id",
        case["initial_docs"],
    )

    async def no_notify(*_args, **_kwargs):
        return None
    monkeypatch.setattr(submission_router, "notify", no_notify)
    owner = case["users"]["business_a"]
    result1 = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]),
        req=submission_router.ResubmitIn(new_document_ids=[str(x) for x in case["round1_docs"]], business_notes="Round 1 response"),
        request=synthetic_request(), owner=owner, db=db,
    )
    assert result1["round_resolved"] == 1
    first_state = await db.fetchrow("SELECT status, revision_round, document_ids FROM submissions WHERE id=$1", case["ids"]["submission"])
    assert first_state["status"] == "reviewing"
    assert first_state["revision_round"] == 1
    assert first_state["document_ids"] == case["round1_docs"]

    await _request_revision(monkeypatch, db, case, "Round 2 synthetic feedback")
    result2 = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]),
        req=submission_router.ResubmitIn(new_document_ids=[str(x) for x in case["round2_docs"]], business_notes="Round 2 response"),
        request=synthetic_request(), owner=owner, db=db,
    )
    assert result2["round_resolved"] == 2

    history = await submission_router.get_revision_history(
        str(case["ids"]["submission"]), user=case["users"]["cb_p"], db=db,
    )
    assert [item["round"] for item in history["history"]] == [2, 1]
    by_round = {item["round"]: item for item in history["history"]}
    assert by_round[1]["submitted_document_ids"] == [str(x) for x in case["initial_docs"]]
    assert by_round[2]["submitted_document_ids"] == [str(x) for x in case["round1_docs"]]
    assert by_round[1]["requirements_version_id"] == str(case["ids"]["requirements"])

    current_old_row = await db.fetchrow(
        """SELECT id, round, requester_id, requester_name, feedback, document_feedback,
                  requirements_version_id, submitted_document_ids, submitted_round, requested_at
           FROM submission_revision_requests WHERE submission_id=$1 AND round=1""",
        case["ids"]["submission"],
    )
    assert hashlib.sha256(json.dumps(dict(current_old_row), default=str, sort_keys=True).encode()).hexdigest() == old_hash
    current_file_meta = await db.fetch(
        "SELECT id, file_path, file_size, version_number FROM documents WHERE id=ANY($1::uuid[]) ORDER BY id",
        case["initial_docs"],
    )
    assert [dict(row) for row in current_file_meta] == [dict(row) for row in old_file_meta]

    old_by_type = {case["docs"][key]["doc_type"]: case["docs"][key] for key in ("permit-v1", "manual-v1", "support-v1", "extra-v1")}
    new_by_type = {case["docs"][key]["doc_type"]: case["docs"][key] for key in ("permit-v2", "manual-v1", "support-v2", "certificate-v1")}
    retained = {kind for kind in old_by_type.keys() & new_by_type.keys() if old_by_type[kind]["id"] == new_by_type[kind]["id"]}
    replaced = {kind for kind in old_by_type.keys() & new_by_type.keys() if new_by_type[kind]["version_number"] > old_by_type[kind]["version_number"]}
    removed = old_by_type.keys() - new_by_type.keys()
    added = new_by_type.keys() - old_by_type.keys()
    assert retained == {"manual"}
    assert replaced == {"permit", "supporting"}
    assert removed == {"legacy-extra"}
    assert added == {"certificate"}


@pytest.mark.asyncio
async def test_historical_round_document_file_serves_exact_bytes_and_scopes_provider(db, case, monkeypatch, tmp_path):
    # Contract: a CB can reopen evidence pinned to a prior submitted round,
    # but cannot fetch an unrelated same-tenant document. Only Keycloak
    # identity enrichment is stubbed; the real route handler, app-role SQL and
    # FileResponse stream execute against task-owned DB/storage bytes.
    actor = case["users"]["cb_p"]
    prior_document_id = case["docs"]["manual-v1"]["id"]
    expected_bytes = b"synthetic-prior-round-file-bytes\x00manual-v1"
    file_path = tmp_path / "round-1-manual-v1.pdf"
    file_path.write_bytes(expected_bytes)
    await db.execute(
        "UPDATE documents SET file_path=$1, file_size=$2 WHERE id=$3",
        str(file_path), len(expected_bytes), prior_document_id,
    )

    # Advance the submission pointer to a later round while retaining the
    # earlier exact document ID in the immutable round snapshot.
    await _request_revision(monkeypatch, db, case, "Round 1 request")
    async def no_notify(*_args, **_kwargs):
        return None
    monkeypatch.setattr(submission_router, "notify", no_notify)
    owner = case["users"]["business_a"]
    await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]),
        req=submission_router.ResubmitIn(
            new_document_ids=[str(x) for x in case["round1_docs"]],
            business_notes="Round 1 response",
        ),
        request=synthetic_request(), owner=owner, db=db,
    )
    await _request_revision(monkeypatch, db, case, "Round 2 request")
    await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]),
        req=submission_router.ResubmitIn(
            new_document_ids=[str(x) for x in case["round2_docs"]],
            business_notes="Round 2 response",
        ),
        request=synthetic_request(), owner=owner, db=db,
    )
    current = await db.fetchval(
        "SELECT document_ids FROM submissions WHERE id=$1", case["ids"]["submission"],
    )
    assert prior_document_id not in current
    assert await db.fetchval(
        "SELECT $1=ANY(submitted_document_ids) FROM submission_revision_requests WHERE submission_id=$2 AND round=2",
        prior_document_id, case["ids"]["submission"],
    ) is True

    async def synthetic_identity(_request, _token):
        return actor
    monkeypatch.setattr(document_router, "_get_user_from_header_or_query", synthetic_identity)
    request = synthetic_request()
    response = await document_router.get_document_file(
        doc_id=str(prior_document_id), request=request, token=None, db=db,
    )
    sent: list[dict] = []
    async def send(message):
        sent.append(message)
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    await response(request.scope, receive, send)
    status = next(message["status"] for message in sent if message["type"] == "http.response.start")
    assert status == 200
    served = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    assert served == expected_bytes
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()
    assert hashlib.sha256(served).hexdigest() == expected_hash

    # Download lifecycle must distinguish authorization, response start, and
    # a complete ASGI body; the direct file endpoint issues no signed URL.
    started_event = await db.fetchrow(
        "SELECT metadata FROM audit_logs WHERE action='document.download_response_started' AND entity_id=$1",
        str(prior_document_id),
    )
    served_event = await db.fetchrow(
        "SELECT metadata FROM audit_logs WHERE action='document.download_bytes_served' AND entity_id=$1",
        str(prior_document_id),
    )
    assert started_event is not None and served_event is not None
    started_meta = started_event["metadata"] if isinstance(started_event["metadata"], dict) else json.loads(started_event["metadata"])
    served_meta = served_event["metadata"] if isinstance(served_event["metadata"], dict) else json.loads(served_event["metadata"])
    assert started_meta["lifecycle"] == "response_started"
    assert served_meta["lifecycle"] == "body_complete"
    assert served_meta["bytes_sent"] == len(expected_bytes)
    assert served_meta["delivery_mode"] == "asgi_body"
    assert served_meta["url_issued"] is False
    assert await db.fetchval(
        "SELECT count(*) FROM audit_logs WHERE action='document.download_url_issued' AND entity_id=$1",
        str(prior_document_id),
    ) == 0

    # A failed send is logged as interrupted, not as completed bytes served.
    aborted_response = await document_router.get_document_file(
        doc_id=str(prior_document_id), request=request, token=None, db=db,
    )
    async def fail_after_response_start(message):
        if message["type"] == "http.response.body":
            raise OSError("synthetic client disconnect")
    with pytest.raises(OSError, match="synthetic client disconnect"):
        await aborted_response(request.scope, receive, fail_after_response_start)
    aborted_event = await db.fetchrow(
        "SELECT metadata FROM audit_logs WHERE action='document.download_interrupted' AND entity_id=$1 ORDER BY created_at DESC LIMIT 1",
        str(prior_document_id),
    )
    assert aborted_event is not None
    aborted_meta = aborted_event["metadata"] if isinstance(aborted_event["metadata"], dict) else json.loads(aborted_event["metadata"])
    assert aborted_meta["lifecycle"] == "interrupted_before_body_complete"
    assert aborted_meta["bytes_sent"] == 0

    event = await db.fetchrow(
        """SELECT metadata FROM audit_logs
           WHERE action='document.download_authorized' AND entity_id=$1""",
        str(prior_document_id),
    )
    assert event is not None
    metadata = event["metadata"] if isinstance(event["metadata"], dict) else json.loads(event["metadata"])
    assert metadata["lifecycle"] == "authorized_before_response"
    assert metadata["document_version_id"] == str(prior_document_id)
    assert metadata["version_number"] == 1
    assert metadata["round"] == 2

    # Preview and original-file readers share the same current authorization.
    preview = await document_router.preview_document(
        doc_id=str(prior_document_id), request=request, token=None, db=db,
    )
    preview_messages: list[dict] = []
    async def preview_send(message):
        preview_messages.append(message)
    await preview(request.scope, receive, preview_send)
    preview_bytes = b"".join(
        message.get("body", b"") for message in preview_messages
        if message["type"] == "http.response.body"
    )
    assert preview_bytes == expected_bytes
    assert hashlib.sha256(preview_bytes).hexdigest() == expected_hash

    selected_actor = actor
    async def selected_identity(_request, _token):
        return selected_actor
    monkeypatch.setattr(document_router, "_get_user_from_header_or_query", selected_identity)

    async def stream_file_as(selected):
        nonlocal selected_actor
        selected_actor = selected
        file_response = await document_router.get_document_file(
            doc_id=str(prior_document_id), request=request, token=None, db=db,
        )
        messages: list[dict] = []
        async def send_file(message):
            messages.append(message)
        await file_response(request.scope, receive, send_file)
        file_status = next(message["status"] for message in messages if message["type"] == "http.response.start")
        file_bytes = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        return file_status, file_bytes

    # Assigned reviewer can read the current packet and exact pinned historical bytes.
    assigned = case["users"]["assigned"]
    assigned_packet = await submission_router.submission_documents(
        submission_id=str(case["ids"]["submission"]), user=assigned, db=db,
    )
    current_packet_ids = {str(doc_id) for doc_id in case["round2_docs"]}
    assert current_packet_ids <= {item["id"] for item in assigned_packet["documents"]}
    assigned_status, assigned_bytes = await stream_file_as(assigned)
    assert assigned_status == 200 and assigned_bytes == expected_bytes

    # Reassignment revokes the old reviewer immediately and grants the new reviewer.
    replacement_reviewer = case["users"]["unassigned"]
    await db.execute(
        "UPDATE submissions SET auditor_id=$1 WHERE id=$2",
        replacement_reviewer["id"], case["ids"]["submission"],
    )
    with pytest.raises(HTTPException) as old_packet:
        await submission_router.submission_documents(
            submission_id=str(case["ids"]["submission"]), user=assigned, db=db,
        )
    assert old_packet.value.status_code == 404
    with pytest.raises(HTTPException) as old_file:
        await stream_file_as(assigned)
    assert old_file.value.status_code == 404
    new_packet = await submission_router.submission_documents(
        submission_id=str(case["ids"]["submission"]), user=replacement_reviewer, db=db,
    )
    assert current_packet_ids <= {item["id"] for item in new_packet["documents"]}
    new_status, new_bytes = await stream_file_as(replacement_reviewer)
    assert new_status == 200 and new_bytes == expected_bytes
    await db.execute(
        "UPDATE submissions SET auditor_id=$1 WHERE id=$2",
        assigned["id"], case["ids"]["submission"],
    )

    # Wrong CB, unassigned provider, and wrong Business do not reach storage.
    for actor_key in ("cb_q", "unassigned", "business_b"):
        selected_actor = case["users"][actor_key]
        with pytest.raises(HTTPException) as denied:
            await document_router.get_document_file(
                doc_id=str(prior_document_id), request=request, token=None, db=db,
            )
        assert denied.value.status_code == 404
    assert await db.fetchval(
        "SELECT count(*) FROM audit_logs WHERE action='document.download_authorized' AND entity_id=$1",
        str(prior_document_id),
    ) == 4

    # Revocation/reassignment is evaluated on the next historical access.
    await db.execute(
        "UPDATE submissions SET provider_id=$1 WHERE id=$2",
        case["ids"]["cb_q"], case["ids"]["submission"],
    )
    selected_actor = actor
    with pytest.raises(HTTPException) as revoked:
        await document_router.get_document_file(
            doc_id=str(prior_document_id), request=request, token=None, db=db,
        )
    assert revoked.value.status_code == 404

    # Newly linked CB owner sees the packet and round-pinned historical bytes.
    current_cb_owner = case["users"]["cb_q"]
    new_owner_packet = await submission_router.submission_documents(
        submission_id=str(case["ids"]["submission"]), user=current_cb_owner, db=db,
    )
    assert current_packet_ids <= {item["id"] for item in new_owner_packet["documents"]}
    owner_status, owner_bytes = await stream_file_as(current_cb_owner)
    assert owner_status == 200 and owner_bytes == expected_bytes

    # A document never submitted in this submission's history stays invisible.
    selected_actor = current_cb_owner
    unrelated_document_id = case["docs"]["wrong-v1"]["id"]
    with pytest.raises(HTTPException) as exc:
        await document_router.get_document_file(
            doc_id=str(unrelated_document_id), request=request, token=None, db=db,
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Tài liệu không tồn tại"


@pytest.mark.asyncio
async def test_request_revision_retry_same_key_replays_original_request(db, case):
    request = synthetic_request(headers={"Idempotency-Key": "synthetic-revision-request-key"})
    payload = submission_router.RequestRevisionIn(
        feedback="same revision request payload",
        document_feedback=[submission_router.DocumentFeedbackIn(
            document_id=str(case["initial_docs"][0]), issue="required evidence", severity="major", suggestion="upload exact version",
        )],
    )
    first = await submission_router.provider_request_revision(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=request, user=case["users"]["assigned"], db=db,
    )
    second = await submission_router.provider_request_revision(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=request, user=case["users"]["assigned"], db=db,
    )
    assert second == first
    assert await db.fetchval(
        "SELECT revision_round FROM submissions WHERE id=$1", case["ids"]["submission"],
    ) == 1
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1", case["ids"]["submission"],
    ) == 1
    changed_payload = submission_router.RequestRevisionIn(
        feedback="different payload under same request key",
        document_feedback=[submission_router.DocumentFeedbackIn(
            document_id=str(case["initial_docs"][0]), issue="different issue", severity="minor", suggestion="different suggestion",
        )],
    )
    with pytest.raises(HTTPException) as exc:
        await submission_router.provider_request_revision(
            submission_id=str(case["ids"]["submission"]), req=changed_payload,
            request=request, user=case["users"]["assigned"], db=db,
        )
    assert exc.value.status_code == 409
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1", case["ids"]["submission"],
    ) == 1


@pytest.mark.asyncio
async def test_submit_retry_same_key_returns_same_submission_receipt(db, case, monkeypatch):
    notify_calls = 0

    async def capture_notify(*_args, **_kwargs):
        nonlocal notify_calls
        notify_calls += 1

    monkeypatch.setattr(submission_router, "notify", capture_notify)
    request = synthetic_request(headers={"Idempotency-Key": "synthetic-submit-retry-key"})
    payload = submission_router.SubmitRequest(
        provider_id=str(case["ids"]["cb_p"]),
        document_ids=[str(document_id) for document_id in case["initial_docs"]],
        notes="synthetic submit retry",
    )
    owner = case["users"]["business_a"]
    first = await submission_router.submit_documents(req=payload, request=request, owner=owner, db=db)
    second = await submission_router.submit_documents(req=payload, request=request, owner=owner, db=db)
    assert second == first
    assert await db.fetchval(
        "SELECT count(*) FROM submissions WHERE id=$1", first["submission_id"],
    ) == 1
    assert notify_calls == 1

    changed_payload = submission_router.SubmitRequest(
        provider_id=str(case["ids"]["cb_p"]),
        document_ids=[str(document_id) for document_id in case["initial_docs"]],
        notes="same key, different notes",
    )
    with pytest.raises(HTTPException) as exc:
        await submission_router.submit_documents(req=changed_payload, request=request, owner=owner, db=db)
    assert exc.value.status_code == 409
    assert await db.fetchval(
        "SELECT count(*) FROM submissions WHERE business_tenant=$1 AND notes IN ($2, $3)",
        owner["tenant_id"], "synthetic submit retry", "same key, different notes",
    ) == 1
    assert notify_calls == 1


@pytest.mark.asyncio
async def test_submit_route_concurrent_same_key_commits_one_submission(db, case, monkeypatch):
    import auth.audit_router as audit_router

    other = await asyncpg.connect(os.environ["DATABASE_URL"])
    entered_notify = asyncio.Event()
    release_notify = asyncio.Event()
    second_helper_entered = asyncio.Event()
    notify_calls = 0
    helper_calls = 0
    original_helper = audit_router._execute_mobile_replay_operation

    async def blocked_notify(*_args, **_kwargs):
        nonlocal notify_calls
        notify_calls += 1
        entered_notify.set()
        await release_notify.wait()

    async def tracked_helper(**kwargs):
        nonlocal helper_calls
        helper_calls += 1
        if helper_calls == 2:
            second_helper_entered.set()
        return await original_helper(**kwargs)

    monkeypatch.setattr(submission_router, "notify", blocked_notify)
    monkeypatch.setattr(audit_router, "_execute_mobile_replay_operation", tracked_helper)
    request = synthetic_request(headers={"Idempotency-Key": f"concurrent-submit-{uuid4()}"})
    owner = case["users"]["business_a"]
    payload = submission_router.SubmitRequest(
        provider_id=str(case["ids"]["cb_p"]),
        document_ids=[str(document_id) for document_id in case["initial_docs"]],
        notes="concurrent synthetic submit",
    )

    async def invoke(connection):
        return await submission_router.submit_documents(
            req=payload, request=request, owner=owner, db=connection,
        )

    first = asyncio.create_task(invoke(db))
    try:
        await asyncio.wait_for(entered_notify.wait(), timeout=10)
        second = asyncio.create_task(invoke(other))
        await asyncio.wait_for(second_helper_entered.wait(), timeout=10)
        release_notify.set()
        first_result, second_result = await asyncio.gather(first, second)
        assert first_result == second_result
        assert notify_calls == 1
        assert await db.fetchval(
            "SELECT count(*) FROM submissions WHERE business_tenant=$1 AND notes=$2",
            owner["tenant_id"], "concurrent synthetic submit",
        ) == 1
        assert await db.fetchval(
            """SELECT count(*) FROM mobile_offline_replay_operations
               WHERE tenant_id=$1 AND operation_type='submission.submit'
                 AND resource_key=$2 AND idempotency_key=$3""",
            owner["tenant_id"],
            f"provider:{case['ids']['cb_p']}:actor:{owner['id']}",
            request.headers["idempotency-key"],
        ) == 1
    finally:
        release_notify.set()
        await other.close()


@pytest.mark.asyncio
async def test_submit_replay_rechecks_current_provider_eligibility(db, case, monkeypatch):
    async def no_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(submission_router, "notify", no_notify)
    request = synthetic_request(headers={"Idempotency-Key": f"eligibility-{uuid4()}"})
    owner = case["users"]["business_a"]
    payload = submission_router.SubmitRequest(
        provider_id=str(case["ids"]["cb_p"]),
        document_ids=[str(document_id) for document_id in case["initial_docs"]],
        notes="synthetic eligibility replay",
    )
    first = await submission_router.submit_documents(req=payload, request=request, owner=owner, db=db)
    await db.execute("UPDATE users SET status='suspended' WHERE id=$1", case["ids"]["cb_p"])
    with pytest.raises(HTTPException) as exc:
        await submission_router.submit_documents(req=payload, request=request, owner=owner, db=db)
    assert exc.value.status_code == 404
    assert await db.fetchval(
        "SELECT count(*) FROM submissions WHERE id=$1", first["submission_id"],
    ) == 1


@pytest.mark.asyncio
async def test_submit_failure_rolls_back_receipt_and_submission(db, case, monkeypatch):
    async def fail_notify(*_args, **_kwargs):
        raise RuntimeError("synthetic notification failure")

    monkeypatch.setattr(submission_router, "notify", fail_notify)
    request = synthetic_request(headers={"Idempotency-Key": "synthetic-submit-rollback"})
    owner = case["users"]["business_a"]
    payload = submission_router.SubmitRequest(
        provider_id=str(case["ids"]["cb_p"]),
        document_ids=[str(document_id) for document_id in case["initial_docs"]],
        notes="synthetic submit rollback",
    )
    with pytest.raises(RuntimeError, match="synthetic notification failure"):
        await submission_router.submit_documents(req=payload, request=request, owner=owner, db=db)
    assert await db.fetchval(
        "SELECT count(*) FROM submissions WHERE business_tenant=$1 AND notes=$2",
        owner["tenant_id"], "synthetic submit rollback",
    ) == 0
    assert await db.fetchval(
        "SELECT count(*) FROM mobile_offline_replay_operations WHERE idempotency_key=$1",
        "synthetic-submit-rollback",
    ) == 0


@pytest.mark.asyncio
async def test_resubmit_retry_same_key_returns_same_logical_result(db, case, monkeypatch):
    """R5 RED: retry after a committed response loss must replay its receipt."""
    await _request_revision(monkeypatch, db, case, "Synthetic idempotent resubmit")

    async def no_notify(*_args, **_kwargs):
        return None
    monkeypatch.setattr(submission_router, "notify", no_notify)

    request = synthetic_request(headers={"Idempotency-Key": "synthetic-resubmit-key-001"})
    owner = case["users"]["business_a"]
    payload = submission_router.ResubmitIn(
        new_document_ids=[str(doc_id) for doc_id in case["round1_docs"]],
        business_notes="same canonical payload",
    )
    first = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]),
        req=payload, request=request, owner=owner, db=db,
    )
    # Simulate the client retrying because it did not receive the committed response.
    second = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]),
        req=payload, request=request, owner=owner, db=db,
    )
    assert second == first
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1",
        case["ids"]["submission"],
    ) == 1
    assert await db.fetchval(
        "SELECT revision_round FROM submissions WHERE id=$1",
        case["ids"]["submission"],
    ) == 1


@pytest.mark.asyncio
async def test_resubmit_same_key_different_payload_conflicts_without_mutation(db, case, monkeypatch):
    await _request_revision(monkeypatch, db, case, "Synthetic idempotent conflict")

    async def no_notify(*_args, **_kwargs):
        return None
    monkeypatch.setattr(submission_router, "notify", no_notify)
    request = synthetic_request(headers={"Idempotency-Key": "synthetic-resubmit-key-conflict"})
    owner = case["users"]["business_a"]
    kwargs = {
        "submission_id": str(case["ids"]["submission"]),
        "request": request,
        "owner": owner,
        "db": db,
    }
    first_payload = submission_router.ResubmitIn(
        new_document_ids=[str(doc_id) for doc_id in case["round1_docs"]],
        business_notes="first payload",
    )
    await submission_router.business_resubmit(req=first_payload, **kwargs)

    changed_payload = submission_router.ResubmitIn(
        new_document_ids=[str(doc_id) for doc_id in case["round1_docs"]],
        business_notes="different payload under same key",
    )
    with pytest.raises(HTTPException) as exc:
        await submission_router.business_resubmit(req=changed_payload, **kwargs)
    assert exc.value.status_code == 409
    row = await db.fetchrow(
        "SELECT status, revision_round FROM submissions WHERE id=$1",
        case["ids"]["submission"],
    )
    assert row["status"] == "reviewing"
    assert row["revision_round"] == 1
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1",
        case["ids"]["submission"],
    ) == 1
    assert await db.fetchval(
        "SELECT count(*) FROM mobile_offline_replay_operations WHERE idempotency_key=$1 AND resource_key=$2",
        "synthetic-resubmit-key-conflict",
        f"{case['ids']['submission']}:actor:{case['users']['business_a']['id']}",
    ) == 1


@pytest.mark.asyncio
async def test_resubmit_receipt_and_mutation_rollback_together_on_side_effect_failure(db, case, monkeypatch):
    await _request_revision(monkeypatch, db, case, "Synthetic atomicity")

    async def fail_notify(*_args, **_kwargs):
        raise RuntimeError("synthetic notification failure")
    monkeypatch.setattr(submission_router, "notify", fail_notify)
    request = synthetic_request(headers={"Idempotency-Key": "synthetic-resubmit-rollback"})
    payload = submission_router.ResubmitIn(
        new_document_ids=[str(doc_id) for doc_id in case["round1_docs"]],
        business_notes="atomic mutation",
    )
    with pytest.raises(RuntimeError, match="synthetic notification failure"):
        await submission_router.business_resubmit(
            submission_id=str(case["ids"]["submission"]),
            req=payload,
            request=request,
            owner=case["users"]["business_a"],
            db=db,
        )
    row = await db.fetchrow(
        "SELECT status, revision_round, document_ids FROM submissions WHERE id=$1",
        case["ids"]["submission"],
    )
    assert row["status"] == "revision_required"
    assert row["revision_round"] == 1
    assert [str(doc_id) for doc_id in row["document_ids"]] == [str(doc_id) for doc_id in case["initial_docs"]]
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1 AND resolved_at IS NOT NULL",
        case["ids"]["submission"],
    ) == 0
    assert await db.fetchval(
        "SELECT count(*) FROM mobile_offline_replay_operations WHERE idempotency_key=$1",
        "synthetic-resubmit-rollback",
    ) == 0


@pytest.mark.asyncio
async def test_resubmit_replay_receipt_serializes_concurrent_same_key(db, case):
    from auth.audit_router import _execute_mobile_replay_operation
    from auth.offline_replay_idempotency import build_operation_scope, stable_request_hash

    other = await asyncpg.connect(os.environ["DATABASE_URL"])
    entered_mutation = asyncio.Event()
    release_mutation = asyncio.Event()
    second_started = asyncio.Event()
    mutation_count = 0
    try:
        scope = build_operation_scope(
            tenant_id=case["users"]["business_a"]["tenant_id"],
            user_id=case["users"]["business_a"]["id"],
            visit_id=None,
            operation_type="submission.resubmit.concurrent-test",
            route_key="POST:/submissions/{submission_id}/resubmit",
            resource_key=f"{case['ids']['submission']}:actor:{case['users']['business_a']['id']}",
            idempotency_key=f"concurrent-{uuid4()}",
        )
        request_hash = stable_request_hash(
            payload={"new_document_ids": [str(x) for x in case["round1_docs"]], "business_notes": "concurrent"},
            resource_identity={"tenant_id": scope["tenant_id"], "user_id": scope["user_id"], "submission_id": str(case["ids"]["submission"])},
        )

        async def mutate():
            nonlocal mutation_count
            mutation_count += 1
            entered_mutation.set()
            await release_mutation.wait()
            return {"receipt": "synthetic-stable-result", "round_resolved": 1}

        first = asyncio.create_task(_execute_mobile_replay_operation(
            db=db, scope=scope, request_hash=request_hash, mutate=mutate,
        ))
        await entered_mutation.wait()

        async def replay():
            second_started.set()
            return await _execute_mobile_replay_operation(
                db=other, scope=scope, request_hash=request_hash,
                mutate=lambda: pytest.fail("duplicate concurrent command executed mutation"),
            )

        second = asyncio.create_task(replay())
        await second_started.wait()
        release_mutation.set()
        first_result, second_result = await asyncio.gather(first, second)
        assert first_result == second_result == {"receipt": "synthetic-stable-result", "round_resolved": 1}
        assert mutation_count == 1
    finally:
        release_mutation.set()
        await other.close()


@pytest.mark.asyncio
async def test_request_revision_with_second_key_is_rejected_as_stale_without_receipt(db, case, monkeypatch):
    async def no_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(submission_router, "notify", no_notify)
    payload = submission_router.RequestRevisionIn(feedback="First request", document_feedback=[])
    user = case["users"]["assigned"]
    first_request = synthetic_request(headers={"Idempotency-Key": f"revision-first-{uuid4()}"})
    second_request = synthetic_request(headers={"Idempotency-Key": f"revision-stale-{uuid4()}"})
    await submission_router.provider_request_revision(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=first_request, user=user, db=db,
    )
    with pytest.raises(HTTPException) as exc:
        await submission_router.provider_request_revision(
            submission_id=str(case["ids"]["submission"]), req=payload,
            request=second_request, user=user, db=db,
        )
    assert exc.value.status_code == 400
    assert await db.fetchval(
        "SELECT revision_round FROM submissions WHERE id=$1", case["ids"]["submission"],
    ) == 1
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1", case["ids"]["submission"],
    ) == 1
    assert await db.fetchval(
        "SELECT count(*) FROM mobile_offline_replay_operations WHERE idempotency_key=$1",
        second_request.headers["idempotency-key"],
    ) == 0


@pytest.mark.asyncio
async def test_resubmit_with_second_key_stale_state_is_a_noop_without_duplicate_side_effects(db, case, monkeypatch):
    notify_calls = 0

    async def count_notify(*_args, **_kwargs):
        nonlocal notify_calls
        notify_calls += 1

    await _request_revision(monkeypatch, db, case, "Synthetic stale resubmit")
    monkeypatch.setattr(submission_router, "notify", count_notify)
    owner = case["users"]["business_a"]
    payload = submission_router.ResubmitIn(
        new_document_ids=[str(doc_id) for doc_id in case["round1_docs"]],
        business_notes="synthetic stale-state resubmit",
    )
    first = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=synthetic_request(headers={"Idempotency-Key": f"resubmit-first-{uuid4()}"}),
        owner=owner, db=db,
    )
    audit_count = await db.fetchval(
        "SELECT count(*) FROM audit_logs WHERE action='submission.resubmitted' AND entity_id=$1",
        str(case["ids"]["submission"]),
    )
    second = await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=synthetic_request(headers={"Idempotency-Key": f"resubmit-stale-{uuid4()}"}),
        owner=owner, db=db,
    )
    assert second["resubmitted_at"] == first["resubmitted_at"]
    assert await db.fetchval(
        "SELECT status FROM submissions WHERE id=$1", case["ids"]["submission"],
    ) == "reviewing"
    assert await db.fetchval(
        "SELECT revision_round FROM submissions WHERE id=$1", case["ids"]["submission"],
    ) == 1
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1 AND resolved_at IS NOT NULL",
        case["ids"]["submission"],
    ) == 1
    assert await db.fetchval(
        "SELECT count(*) FROM audit_logs WHERE action='submission.resubmitted' AND entity_id=$1",
        str(case["ids"]["submission"]),
    ) == audit_count
    assert notify_calls == 1


@pytest.mark.asyncio
async def test_request_revision_replay_rechecks_current_assignment(db, case, monkeypatch):
    async def no_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(submission_router, "notify", no_notify)
    request = synthetic_request(headers={"Idempotency-Key": f"assigned-replay-{uuid4()}"})
    payload = submission_router.RequestRevisionIn(feedback="Current assignment", document_feedback=[])
    assigned = case["users"]["assigned"]
    await submission_router.provider_request_revision(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=request, user=assigned, db=db,
    )
    await db.execute(
        "UPDATE submissions SET auditor_id=$1 WHERE id=$2",
        case["users"]["unassigned"]["id"], case["ids"]["submission"],
    )
    with pytest.raises(HTTPException) as exc:
        await submission_router.provider_request_revision(
            submission_id=str(case["ids"]["submission"]), req=payload,
            request=request, user=assigned, db=db,
        )
    assert exc.value.status_code == 404
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1",
        case["ids"]["submission"],
    ) == 1


@pytest.mark.asyncio
async def test_resubmit_replay_rechecks_current_business_scope(db, case, monkeypatch):
    await _request_revision(monkeypatch, db, case, "Synthetic current owner scope")
    request = synthetic_request(headers={"Idempotency-Key": f"owner-scope-{uuid4()}"})
    payload = submission_router.ResubmitIn(new_document_ids=None, business_notes="scope check")
    await submission_router.business_resubmit(
        submission_id=str(case["ids"]["submission"]), req=payload,
        request=request, owner=case["users"]["business_a"], db=db,
    )
    with pytest.raises(HTTPException) as exc:
        await submission_router.business_resubmit(
            submission_id=str(case["ids"]["submission"]), req=payload,
            request=request, owner=case["users"]["business_b"], db=db,
        )
    assert exc.value.status_code == 403
    assert await db.fetchval(
        "SELECT revision_round FROM submissions WHERE id=$1", case["ids"]["submission"],
    ) == 1


@pytest.mark.asyncio
async def test_resubmit_route_concurrent_different_keys_has_one_winner(db, case, monkeypatch):
    await _request_revision(monkeypatch, db, case, "Synthetic concurrent stale state")
    other = await asyncpg.connect(os.environ["DATABASE_URL"])
    arrived = 0
    barrier = asyncio.Event()
    barrier_lock = asyncio.Lock()

    class StaleSnapshotConnection:
        def __init__(self, inner):
            self.inner = inner

        def __getattr__(self, name):
            return getattr(self.inner, name)

        async def fetchrow(self, sql, *args):
            nonlocal arrived
            row = await self.inner.fetchrow(sql, *args)
            if "SELECT id, status, revision_round, revision_resubmitted_at" in sql:
                async with barrier_lock:
                    arrived += 1
                    if arrived == 2:
                        barrier.set()
                await asyncio.wait_for(barrier.wait(), timeout=10)
            return row

    async def no_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(submission_router, "notify", no_notify)
    db_a = StaleSnapshotConnection(db)
    db_b = StaleSnapshotConnection(other)
    owner = case["users"]["business_a"]
    payload = submission_router.ResubmitIn(
        new_document_ids=[str(doc_id) for doc_id in case["round1_docs"]],
        business_notes="competing resubmit",
    )

    async def invoke(connection, key):
        return await submission_router.business_resubmit(
            submission_id=str(case["ids"]["submission"]), req=payload,
            request=synthetic_request(headers={"Idempotency-Key": key}),
            owner=owner, db=connection,
        )

    try:
        outcomes = await asyncio.gather(
            invoke(db_a, f"competing-a-{uuid4()}"),
            invoke(db_b, f"competing-b-{uuid4()}"),
            return_exceptions=True,
        )
        successes = [outcome for outcome in outcomes if isinstance(outcome, dict)]
        failures = [outcome for outcome in outcomes if isinstance(outcome, HTTPException)]
        assert len(successes) == len(failures) == 1
        assert failures[0].status_code == 400
        assert await db.fetchval(
            "SELECT status FROM submissions WHERE id=$1", case["ids"]["submission"],
        ) == "reviewing"
        assert await db.fetchval(
            "SELECT revision_round FROM submissions WHERE id=$1", case["ids"]["submission"],
        ) == 1
        assert await db.fetchval(
            "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1 AND resolved_at IS NOT NULL",
            case["ids"]["submission"],
        ) == 1
        assert await db.fetchval(
            "SELECT count(*) FROM audit_logs WHERE action='submission.resubmitted' AND entity_id=$1",
            str(case["ids"]["submission"]),
        ) == 1
    finally:
        await other.close()


@pytest.mark.asyncio
async def test_request_revision_route_concurrent_different_keys_has_one_winner(db, case, monkeypatch):
    other = await asyncpg.connect(os.environ["DATABASE_URL"])
    arrived = 0
    barrier = asyncio.Event()
    barrier_lock = asyncio.Lock()

    class StaleSnapshotConnection:
        def __init__(self, inner):
            self.inner = inner

        def __getattr__(self, name):
            return getattr(self.inner, name)

        async def fetchrow(self, sql, *args):
            nonlocal arrived
            row = await self.inner.fetchrow(sql, *args)
            if "SELECT id, status, revision_round, business_tenant, requirements_version_id" in sql:
                async with barrier_lock:
                    arrived += 1
                    if arrived == 2:
                        barrier.set()
                await asyncio.wait_for(barrier.wait(), timeout=10)
            return row

    notify_calls = 0

    async def count_notify(*_args, **_kwargs):
        nonlocal notify_calls
        notify_calls += 1

    monkeypatch.setattr(submission_router, "notify", count_notify)
    db_a, db_b = StaleSnapshotConnection(db), StaleSnapshotConnection(other)
    assigned = case["users"]["assigned"]
    payload = submission_router.RequestRevisionIn(feedback="competing revision requests", document_feedback=[])

    async def invoke(connection, key):
        return await submission_router.provider_request_revision(
            submission_id=str(case["ids"]["submission"]), req=payload,
            request=synthetic_request(headers={"Idempotency-Key": key}),
            user=assigned, db=connection,
        )

    try:
        outcomes = await asyncio.gather(
            invoke(db_a, f"request-a-{uuid4()}"),
            invoke(db_b, f"request-b-{uuid4()}"),
            return_exceptions=True,
        )
        successes = [outcome for outcome in outcomes if isinstance(outcome, dict)]
        failures = [outcome for outcome in outcomes if isinstance(outcome, HTTPException)]
        assert len(successes) == len(failures) == 1
        assert failures[0].status_code == 400
        assert await db.fetchval(
            "SELECT status FROM submissions WHERE id=$1", case["ids"]["submission"],
        ) == "revision_required"
        assert await db.fetchval(
            "SELECT revision_round FROM submissions WHERE id=$1", case["ids"]["submission"],
        ) == 1
        assert await db.fetchval(
            "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1",
            case["ids"]["submission"],
        ) == 1
        assert await db.fetchval(
            "SELECT count(*) FROM mobile_offline_replay_operations WHERE operation_type='submission.request_revision' AND resource_key LIKE $1",
            f"{case['ids']['submission']}:actor:%",
        ) == 1
        assert notify_calls == 1
    finally:
        await other.close()


@pytest.mark.asyncio
async def test_request_revision_route_serializes_concurrent_same_key(db, case, monkeypatch):
    import auth.audit_router as audit_router
    import services.submission_revisions as revision_service

    other = await asyncpg.connect(os.environ["DATABASE_URL"])
    entered_mutation = asyncio.Event()
    release_mutation = asyncio.Event()
    second_helper_entered = asyncio.Event()
    original_service = revision_service.request_revision
    original_helper = audit_router._execute_mobile_replay_operation
    service_calls = 0
    helper_calls = 0

    async def blocked_revision(*args, **kwargs):
        nonlocal service_calls
        service_calls += 1
        entered_mutation.set()
        await release_mutation.wait()
        return await original_service(*args, **kwargs)

    async def tracked_helper(**kwargs):
        nonlocal helper_calls
        helper_calls += 1
        if helper_calls == 2:
            second_helper_entered.set()
        return await original_helper(**kwargs)

    monkeypatch.setattr(revision_service, "request_revision", blocked_revision)
    monkeypatch.setattr(audit_router, "_execute_mobile_replay_operation", tracked_helper)
    request = synthetic_request(headers={"Idempotency-Key": f"concurrent-revision-{uuid4()}"})
    payload = submission_router.RequestRevisionIn(feedback="Concurrent synthetic request", document_feedback=[])
    user = case["users"]["assigned"]

    async def invoke(connection):
        return await submission_router.provider_request_revision(
            submission_id=str(case["ids"]["submission"]), req=payload,
            request=request, user=user, db=connection,
        )

    first = asyncio.create_task(invoke(db))
    try:
        await entered_mutation.wait()
        second = asyncio.create_task(invoke(other))
        await second_helper_entered.wait()
        release_mutation.set()
        first_result, second_result = await asyncio.gather(first, second)
        assert first_result == second_result
        assert service_calls == 1
        assert await db.fetchval(
            "SELECT revision_round FROM submissions WHERE id=$1", case["ids"]["submission"],
        ) == 1
        assert await db.fetchval(
            "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1", case["ids"]["submission"],
        ) == 1
    finally:
        release_mutation.set()
        await other.close()


@pytest.mark.asyncio
async def test_request_revision_database_failure_rolls_back_submission(db, case):
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await request_revision(
            db,
            submission_id=str(case["ids"]["submission"]),
            requester_id=str(uuid4()),
            requester_name="Synthetic missing user",
            feedback="Must roll back",
        )
    row = await db.fetchrow("SELECT status, revision_round FROM submissions WHERE id=$1", case["ids"]["submission"])
    assert row["status"] == "reviewing"
    assert row["revision_round"] == 0
    assert await db.fetchval(
        "SELECT count(*) FROM submission_revision_requests WHERE submission_id=$1",
        case["ids"]["submission"],
    ) == 0


@pytest.mark.asyncio
async def test_g1_dashboard_uses_canonical_tenant_predicate_under_app_role(db, case):
    from auth.dossier_router import _resolve_tenant_id
    from services.dossier_dashboard import build_dashboard

    owner = case["users"]["business_a"]
    # A forged tenant claim must not redirect the dashboard query to Business B.
    actor_with_wrong_claim = {**owner, "tenant_id": str(case["ids"]["business_b"])}
    canonical_tenant = await _resolve_tenant_id(db, actor_with_wrong_claim)
    assert str(canonical_tenant) == str(case["ids"]["business_a"])

    canonical_tenant_id = str(canonical_tenant)
    own_page = await build_dashboard(db, canonical_tenant_id, page=1, page_size=50)
    other_page = await build_dashboard(db, str(case["ids"]["business_b"]), page=1, page_size=50)
    own_ids = {dossier["id"] for profile in own_page["profiles"] for dossier in profile["dossiers"]}
    other_ids = {dossier["id"] for profile in other_page["profiles"] for dossier in profile["dossiers"]}
    assert str(case["ids"]["dossier"]) in own_ids
    assert str(case["ids"]["dossier"]) not in other_ids
    assert other_page["total_dossiers"] == 0


@pytest.mark.asyncio
async def test_legacy_dossier_remains_unknown_under_current_published_profile(db, case):
    from services.dossier_dashboard import build_dashboard

    legacy_id = uuid4()
    owner = case["users"]["business_a"]
    # No requirements_version_id/status supplied: migration default is UNKNOWN.
    await db.execute(
        """INSERT INTO dossiers (id, tenant_id, standard_type_id, title, status, created_by)
           VALUES ($1, $2, $3, 'Synthetic legacy dossier', 'draft', $4)""",
        legacy_id, case["ids"]["business_a"], case["ids"]["standard"], owner["id"],
    )
    dashboard = await build_dashboard(db, str(case["ids"]["business_a"]), page=1, page_size=50)
    dossiers = [d for profile in dashboard["profiles"] for d in profile["dossiers"]]
    legacy = next(d for d in dossiers if d["id"] == str(legacy_id))

    assert legacy["requirements_binding_status"] == "unknown"
    assert legacy["requirements_version_id"] is None
    assert legacy["readiness"]["state"] == "requirements_unknown"
    assert legacy["readiness"]["readiness_percent"] is None
    assert legacy["readiness"]["blocking_reasons"][0]["code"] == "requirements_version_unknown_no_backfill"


@pytest.mark.asyncio
async def test_requirements_publication_authority_snapshot_immutability_and_rollback(db, case):
    from services.requirements_versions import publish_requirements_version

    standard_id = case["ids"]["standard"]
    admin_id = case["users"]["cb_p"]["id"]
    for order, (doc_type, required) in enumerate((("policy", True), ("records", False))):
        await db.execute(
            "INSERT INTO standard_doc_types (standard_type_id, doc_type, required, display_order) VALUES ($1,$2,$3,$4)",
            standard_id, doc_type, required, order,
        )

    non_admin = {"_keycloak": True, "realm_roles": ["provider"], "role": "provider", "sub": "synthetic-provider"}
    with pytest.raises(HTTPException) as denied:
        await publish_requirements_version(db, standard_type_id=standard_id, actor=non_admin, actor_id=admin_id)
    assert denied.value.status_code == 403
    assert await db.fetchval("SELECT count(*) FROM standard_requirement_versions WHERE standard_type_id=$1", standard_id) == 1

    platform_admin = {"_keycloak": True, "realm_roles": ["platform_admin"], "role": "provider", "sub": str(admin_id), "email": case["users"]["cb_p"]["email"]}
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await publish_requirements_version(db, standard_type_id=standard_id, actor=platform_admin, actor_id=uuid4())
    assert await db.fetchval("SELECT count(*) FROM standard_requirement_versions WHERE standard_type_id=$1", standard_id) == 1
    assert await db.fetchval("SELECT count(*) FROM standard_requirement_current_versions WHERE standard_type_id=$1", standard_id) == 0

    first = await publish_requirements_version(db, standard_type_id=standard_id, actor=platform_admin, actor_id=admin_id)
    assert first["version_number"] == 2
    first_id = UUID(first["requirements_version_id"])
    first_slots = await db.fetch(
        "SELECT doc_type, required, display_order FROM standard_requirement_version_slots WHERE requirements_version_id=$1 ORDER BY display_order",
        first_id,
    )
    await db.execute("UPDATE standard_doc_types SET required=false WHERE standard_type_id=$1 AND doc_type='policy'", standard_id)
    second = await publish_requirements_version(db, standard_type_id=standard_id, actor=platform_admin, actor_id=admin_id)
    assert second["version_number"] == 3 and second["requirements_version_id"] != first["requirements_version_id"]
    assert await db.fetch(
        "SELECT doc_type, required, display_order FROM standard_requirement_version_slots WHERE requirements_version_id=$1 ORDER BY display_order",
        first_id,
    ) == first_slots

    with pytest.raises(asyncpg.exceptions.RaiseError, match="Published requirements version slots are immutable"):
        await db.execute("UPDATE standard_requirement_version_slots SET required=false WHERE requirements_version_id=$1 AND doc_type='policy'", first_id)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="Published requirements versions are immutable"):
        await db.execute("UPDATE standard_requirement_versions SET content_sha256=$2 WHERE id=$1", first_id, "0" * 64)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="Requirements binding is immutable"):
        await db.execute(
            "UPDATE dossiers SET requirements_version_id=$2 WHERE id=$1",
            case["ids"]["dossier"], UUID(second["requirements_version_id"]),
        )
    assert await db.fetchval("SELECT requirements_version_id FROM dossiers WHERE id=$1", case["ids"]["dossier"]) == case["ids"]["requirements"]


@pytest.mark.asyncio
async def test_j1_a02_reuses_exact_document_version_and_denies_wrong_tenant(db, case):
    dossier_a = case["ids"]["dossier"]
    dossier_b = uuid4()
    business_a = case["users"]["business_a"]["id"]
    business_b = case["users"]["business_b"]["id"]
    requirements = case["ids"]["requirements"]
    document = case["docs"]["policy-v1"]["id"]
    await db.execute(
        """INSERT INTO dossiers
           (id, tenant_id, standard_type_id, title, status, created_by,
            requirements_version_id, requirements_binding_status)
           VALUES ($1,$2,$3,'Synthetic reuse target','draft',$4,$5,'bound')""",
        dossier_b, business_a, case["ids"]["standard"], business_a, requirements,
    )

    async with db.transaction():
        pinned_a = await validate_dossier_slot(
            db, dossier_id=dossier_a, tenant_id=business_a, doc_type="policy",
        )
        first = await attach_document_reference(
            db, dossier=pinned_a, document_id=document, doc_type="policy",
            actor_id=business_a, idempotency_key=uuid4(), request_sha256=hashlib.sha256(b"reuse-a").hexdigest(),
        )
        pinned_b = await validate_dossier_slot(
            db, dossier_id=dossier_b, tenant_id=business_a, doc_type="policy",
        )
        second = await attach_document_reference(
            db, dossier=pinned_b, document_id=document, doc_type="policy",
            actor_id=business_a, idempotency_key=uuid4(), request_sha256=hashlib.sha256(b"reuse-b").hexdigest(),
        )

    assert first["created"] is True and second["created"] is True
    rows = await db.fetch(
        """SELECT a.dossier_id,a.document_id,a.requirements_version_id,a.doc_type,
                  d.version_number,d.file_path,d.file_size
           FROM dossier_document_attachments a JOIN documents d ON d.id=a.document_id
           WHERE a.document_id=$1 ORDER BY a.dossier_id""",
        document,
    )
    assert len(rows) == 2
    assert {row["dossier_id"] for row in rows} == {dossier_a, dossier_b}
    assert all(row["document_id"] == document for row in rows)
    assert all(row["requirements_version_id"] == requirements for row in rows)
    assert all(row["doc_type"] == "policy" and row["version_number"] == 1 for row in rows)
    assert all(row["file_path"] == case["docs"]["policy-v1"]["file_path"] for row in rows)
    assert all(row["file_size"] == case["docs"]["policy-v1"]["file_size"] for row in rows)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as denied:
        await validate_dossier_slot(
            db, dossier_id=dossier_a, tenant_id=business_b, doc_type="policy",
        )
    assert denied.value.status_code == 404
    assert await db.fetchval(
        "SELECT count(*) FROM dossier_document_attachments WHERE dossier_id=$1 AND document_id=$2",
        dossier_a, document,
    ) == 1


@pytest.mark.asyncio
async def test_bound_resubmit_without_document_ids_revalidates_current_packet(db, case, monkeypatch):
    from services.submission_revisions import resubmit, InvalidStateTransition
    await _request_revision(monkeypatch, db, case, 'Validate browser current packet')
    await db.execute('UPDATE submissions SET document_ids=$1 WHERE id=$2', [case['docs']['wrong-v1']['id']], case['ids']['submission'])
    with pytest.raises(InvalidStateTransition, match='not mapped'):
        await resubmit(db, submission_id=str(case['ids']['submission']), business_notes='current packet')
    assert await db.fetchval('SELECT status FROM submissions WHERE id=$1', case['ids']['submission']) == 'revision_required'
    assert await db.fetchval('SELECT resolved_at FROM submission_revision_requests WHERE submission_id=$1', case['ids']['submission']) is None


@pytest.mark.asyncio
async def test_bound_browser_replacement_attaches_before_pointer_change(db, case, monkeypatch):
    await db.execute('UPDATE submissions SET dossier_id=$1 WHERE id=$2', case['ids']['dossier'], case['ids']['submission'])
    await _request_revision(monkeypatch, db, case, 'Pinned browser replacement')
    old = case['initial_docs'][0]
    new = case['docs']['permit-v2']['id']
    user = case['users']['business_a']
    await submission_router.replace_submission_document(
        submission_id=str(case['ids']['submission']), request={'old_doc_id':str(old),'new_doc_id':str(new)}, user=user,db=db,
    )
    assert await db.fetchval('SELECT document_id FROM dossier_document_attachments WHERE dossier_id=$1 AND document_id=$2',case['ids']['dossier'],new) == new
    assert await db.fetchval('SELECT status FROM submissions WHERE id=$1',case['ids']['submission']) == 'revision_required'
    before = await db.fetchval('SELECT document_ids FROM submissions WHERE id=$1',case['ids']['submission'])
    with pytest.raises(HTTPException) as error:
        await submission_router.replace_submission_document(
            submission_id=str(case['ids']['submission']),request={'old_doc_id':str(new),'new_doc_id':str(case['docs']['wrong-v1']['id'])},user=user,db=db,
        )
    assert error.value.status_code == 409
    assert await db.fetchval('SELECT document_ids FROM submissions WHERE id=$1',case['ids']['submission']) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('explicit_binding', [True, False])
async def test_reused_document_does_not_borrow_another_dossier_review_context(db, case, explicit_binding):
    from services.dossier_readiness import compute_dossier_readiness
    reuse = uuid4()
    await db.execute('''INSERT INTO dossiers
        (id,tenant_id,standard_type_id,title,status,created_by,requirements_version_id,requirements_binding_status)
        VALUES($1,$2,$3,'Synthetic reuse scope','draft',$2,$4,'bound')''',
        reuse,case['ids']['business_a'],case['ids']['standard'],case['ids']['requirements'])
    if explicit_binding:
        await db.execute('UPDATE submissions SET dossier_id=$1 WHERE id=$2',case['ids']['dossier'],case['ids']['submission'])
    for dossier_id in [case['ids']['dossier'],reuse]:
        dossier = await validate_dossier_slot(db,dossier_id=dossier_id,tenant_id=case['ids']['business_a'],doc_type='permit')
        await attach_document_reference(db,dossier=dossier,document_id=case['initial_docs'][0],doc_type='permit',actor_id=case['ids']['business_a'],idempotency_key=uuid4(),request_sha256='a'*64)
    primary = await compute_dossier_readiness(db,dossier_id=str(case['ids']['dossier']),tenant_id=str(case['ids']['business_a']))
    other = await compute_dossier_readiness(db,dossier_id=str(reuse),tenant_id=str(case['ids']['business_a']))
    assert all(slot['submission_id']==str(case['ids']['submission']) for slot in primary['requirement_slots'])
    assert all(slot['submission_id'] is None and slot['submitted_round'] is None for slot in other['requirement_slots'])
