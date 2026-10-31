from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


def _isolated_app():
    """Mount only production dossier routes, avoiding unrelated app startup."""
    from fastapi import FastAPI
    from auth.dossier_router import router

    app = FastAPI()
    app.include_router(router, prefix="/api/dossiers")
    return app


class OverrideDB:
    def __init__(self, db):
        self.db = db

    async def __call__(self):
        return self.db


def _recorded_sql(db: FakeConn, needle: str) -> list[tuple[str, tuple]]:
    return [call for call in db.calls if needle in call[1][0]]


def _approved_docs() -> list[FakeRecord]:
    return [
        FakeRecord(id=uuid4(), doc_type="halal_policy", status="approved", approval_status="approved", compliance_score=95, evaluation_result={}),
        FakeRecord(id=uuid4(), doc_type="has_manual", status="approved", approval_status="approved", compliance_score=96, evaluation_result={}),
    ]


def _base_db(*, dossier_id, tenant_id, standard_id, docs=None, ncrs=None, decision=None, cert=None) -> FakeConn:
    version_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [
        (
            "FROM dossiers",
            FakeRecord(
                id=dossier_id,
                tenant_id=tenant_id,
                standard_type_id=standard_id,
                requirements_version_id=version_id,
                requirements_binding_status="bound",
                status="in_progress",
                title="Pilot dossier",
            ),
        ),
        ("FROM submissions", FakeRecord(id=uuid4(), status="approved", provider_id=uuid4(), requirements_version_id=version_id, document_ids=[])),
        ("FROM audit_logs", FakeRecord(metadata={"document_versions": {
            str(row["id"]): row.get("version_number") or 1
            for row in (docs or []) if row.get("approval_status") == "approved"
        }})),
        ("FROM certification_decisions", decision),
        ("FROM halal_certificates", cert),
    ]
    db.fetch_responses = [
        (
            "FROM standard_requirement_version_slots",
            [
                FakeRecord(doc_type="halal_policy", required=True, display_order=1),
                FakeRecord(doc_type="has_manual", required=True, display_order=2),
            ],
        ),
        ("FROM documents", docs or []),
        ("FROM audit_ncr", ncrs or []),
    ]
    return db


async def test_readiness_blocks_missing_required_documents_and_names_business_next_actor():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    standard_id = uuid4()
    db = _base_db(dossier_id=dossier_id, tenant_id=tenant_id, standard_id=standard_id)

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["readiness_percent"] == 0
    assert result["certificate_issue_blocked"] is True
    assert result["next_actor_role"] == "business"
    assert result["next_action"] == "upload_required_documents"
    assert result["missing_required_documents"] == ["halal_policy", "has_manual"]
    assert any(reason["code"] == "missing_required_document" for reason in result["blocking_reasons"])
    dossier_queries = _recorded_sql(db, "FROM dossiers")
    assert dossier_queries
    assert "tenant_id" in dossier_queries[0][1][0]
    assert dossier_queries[0][1][1] == (str(dossier_id), str(tenant_id))


async def test_readiness_document_query_uses_only_selected_submission_round_evidence():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id, tenant_id, standard_id = uuid4(), uuid4(), uuid4()
    docs = _approved_docs()
    db = _base_db(dossier_id=dossier_id, tenant_id=tenant_id, standard_id=standard_id, docs=docs[:1])
    submission = db.fetchrow_responses[1][1]
    assert submission is not None
    submission["document_ids"] = [docs[0]["id"]]

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["readiness_percent"] == 25
    assert result["missing_required_documents"] == ["has_manual"]
    document_query = next(call for call in _recorded_sql(db, "FROM documents") if "SELECT d.id, d.doc_type" in call[1][0])
    assert "d.id = ANY(COALESCE(" in document_query[1][0]
    assert "$3::uuid[]," in document_query[1][0]
    assert "a.requirements_version_id=" in document_query[1][0]
    assert "legacy.tenant_id=$2" in document_query[1][0]
    assert document_query[1][1] == (str(dossier_id), str(tenant_id), [docs[0]["id"]])


async def test_readiness_exposes_slot_state_and_exact_evidence_version_for_current_round():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id, tenant_id, standard_id = uuid4(), uuid4(), uuid4()
    ai_only = FakeRecord(
        id=uuid4(), doc_type="halal_policy", status="compliant", approval_status=None,
        compliance_score=99, evaluation_result={"overall_status": "compliant"}, version_number=3,
    )
    reviewed = FakeRecord(
        id=uuid4(), doc_type="has_manual", status="approved", approval_status="approved",
        compliance_score=88, evaluation_result={}, version_number=2,
    )
    db = _base_db(dossier_id=dossier_id, tenant_id=tenant_id, standard_id=standard_id, docs=[ai_only, reviewed])
    submission = db.fetchrow_responses[1][1]
    dossier = db.fetchrow_responses[0][1]
    assert submission is not None and dossier is not None
    submission["document_ids"] = [ai_only["id"], reviewed["id"]]
    submission["revision_round"] = 2
    db.fetch_responses[1] = ("FROM documents", [reviewed, ai_only])

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["requirement_slots"] == [
        {"doc_type": "halal_policy", "required": True, "display_order": 1,
         "requirements_version_id": str(dossier["requirements_version_id"]),
         "state": "pending_review", "evidence_document_id": str(ai_only["id"]), "evidence_version": 3,
         "submission_id": str(submission["id"]), "submitted_round": 3},
        {"doc_type": "has_manual", "required": True, "display_order": 2,
         "requirements_version_id": str(dossier["requirements_version_id"]),
         "state": "approved", "evidence_document_id": str(reviewed["id"]), "evidence_version": 2,
         "submission_id": str(submission["id"]), "submitted_round": 3},
    ]
    assert result["readiness_percent"] == 25


async def test_readiness_blocks_uploaded_but_unapproved_documents_without_treating_ai_score_as_approval():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    standard_id = uuid4()
    db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=[
            FakeRecord(id=uuid4(), doc_type="halal_policy", status="uploaded", approval_status="draft", compliance_score=98, evaluation_result={}),
            FakeRecord(id=uuid4(), doc_type="has_manual", status="uploaded", approval_status="draft", compliance_score=92, evaluation_result={}),
        ],
    )

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["readiness_percent"] == 0
    assert result["missing_required_documents"] == []
    assert result["next_action"] == "review_uploaded_documents"
    assert result["next_actor_role"] == "reviewer"
    assert {d["doc_type"] for d in result["unreviewed_documents"]} == {"halal_policy", "has_manual"}
    assert any(reason["code"] == "document_not_approved" for reason in result["blocking_reasons"])


async def test_readiness_surfaces_rejected_document_reason_as_business_blocker():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    standard_id = uuid4()
    db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=[
            FakeRecord(id=uuid4(), doc_type="halal_policy", status="rejected", approval_status="draft", compliance_score=35, evaluation_result={"review_reason": "Missing signed policy"}),
            FakeRecord(id=uuid4(), doc_type="has_manual", status="approved", approval_status="approved", compliance_score=90, evaluation_result={}),
        ],
    )

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["readiness_percent"] == 25
    assert result["next_action"] == "replace_rejected_documents"
    assert result["next_actor_role"] == "business"
    assert result["rejected_documents"] == [
        {"doc_type": "halal_policy", "document_id": str(db.fetch_responses[1][1][0]["id"]), "reason": "Missing signed policy"}
    ]


async def test_readiness_blocks_open_and_in_review_ncrs_with_correct_next_actor():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    standard_id = uuid4()
    docs = _approved_docs()
    open_db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=docs,
        ncrs=[FakeRecord(id=uuid4(), status="open", severity="major", description="CAPA required", corrective_action="", deadline=None)],
    )
    open_result = await compute_dossier_readiness(open_db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))
    assert open_result["readiness_percent"] == 50
    assert open_result["next_action"] == "submit_capa_evidence"
    assert open_result["next_actor_role"] == "business"
    assert open_result["open_ncrs"][0]["status"] == "open"

    review_db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=docs,
        ncrs=[FakeRecord(id=uuid4(), status="in_review", severity="major", description="Evidence submitted", corrective_action="", deadline=None)],
    )
    review_result = await compute_dossier_readiness(review_db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))
    assert review_result["next_action"] == "verify_capa_evidence"
    assert review_result["next_actor_role"] == "auditor"


async def test_readiness_marks_certificate_ready_only_after_approved_decision_and_no_blockers():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    standard_id = uuid4()
    docs = _approved_docs()
    pending_db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=docs,
        decision=FakeRecord(id=uuid4(), status="pending_review", decision_reason=None),
    )
    pending_result = await compute_dossier_readiness(pending_db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))
    assert pending_result["certificate_issue_blocked"] is True
    assert pending_result["next_action"] == "finalize_certification_decision"
    assert pending_result["next_actor_role"] == "decision_maker"

    approved_db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=docs,
        decision=FakeRecord(id=uuid4(), status="approved", decision_reason="Independent approval"),
        cert=FakeRecord(id=uuid4(), cert_number="HALAL-2026-0001", status="active"),
    )
    approved_result = await compute_dossier_readiness(approved_db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))
    assert approved_result["readiness_percent"] == 100
    assert approved_result["certificate_issue_blocked"] is False
    assert approved_result["next_action"] == "certification_ready"
    assert approved_result["safe_public_trace_available"] is True
    submission_queries = [
        call
        for call in _recorded_sql(approved_db, "FROM submissions")
        if "SELECT id, status, provider_id" in call[1][0]
    ]
    assert submission_queries
    submission_sql = submission_queries[0][1][0]
    assert "ORDER BY updated_at DESC NULLS LAST, submitted_at DESC NULLS LAST" in submission_sql
    assert "created_at" not in submission_sql
    assert "FROM documents d" in submission_sql
    assert "d.id = ANY(submissions.document_ids)" in submission_sql
    assert "d.dossier_id = $2" in submission_sql
    assert "ORDER BY updated_at DESC NULLS LAST, submitted_at DESC NULLS LAST, id DESC" in submission_sql
    assert submission_queries[0][1][1] == (
        str(tenant_id), str(dossier_id), approved_db.fetchrow_responses[0][1]["requirements_version_id"]
    )
    decision_queries = _recorded_sql(approved_db, "FROM certification_decisions")
    assert decision_queries
    decision_sql = decision_queries[0][1][0]
    assert "submission_id = $1" in decision_sql
    assert "business_tenant = $2" in decision_sql
    assert "provider_id = $3" in decision_sql
    selected_submission = approved_db.fetchrow_responses[1][1]
    assert selected_submission is not None
    assert decision_queries[0][1][1] == (
        str(selected_submission["id"]),
        str(tenant_id),
        str(selected_submission["provider_id"]),
        1,
        selected_submission["requirements_version_id"],
    )
    certificate_queries = _recorded_sql(approved_db, "FROM halal_certificates")
    assert certificate_queries
    certificate_sql = certificate_queries[0][1][0]
    assert "submission_id = $1" in certificate_sql
    assert certificate_queries[0][1][1][1] == str(tenant_id)


async def test_readiness_scopes_ncrs_to_the_requested_dossier_submission_documents():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    standard_id = uuid4()
    db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=_approved_docs(),
        ncrs=[FakeRecord(id=uuid4(), status="open", severity="major", description="Dossier CAPA required", corrective_action="", deadline=None)],
    )

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["next_action"] == "submit_capa_evidence"
    ncr_queries = _recorded_sql(db, "FROM audit_ncr")
    assert ncr_queries
    ncr_sql = ncr_queries[0][1][0]
    assert "JOIN documents" in ncr_sql
    assert "d.dossier_id = $2" in ncr_sql
    assert "s.id = $4" in ncr_sql
    assert ncr_queries[0][1][1] == (
        str(tenant_id), str(dossier_id), db.fetchrow_responses[0][1]["requirements_version_id"], db.fetchrow_responses[1][1]["id"]
    )


async def test_readiness_denies_cross_tenant_dossier_access():
    from services.dossier_readiness import compute_dossier_readiness

    db = FakeConn()
    db.fetchrow_responses = [("FROM dossiers", None)]

    with pytest.raises(HTTPException) as exc:
        await compute_dossier_readiness(db, dossier_id=str(uuid4()), tenant_id=str(uuid4()))

    assert exc.value.status_code == 404
    assert not any(call[0] == "fetch" for call in db.calls)


def test_readiness_route_rejects_anonymous_before_db_access():
    app = _isolated_app()

    res = TestClient(app).get(f"/api/dossiers/{uuid4()}/readiness")

    assert res.status_code in (401, 403)


def test_provider_from_unassigned_tenant_cannot_read_other_tenant_dossier_readiness(monkeypatch):
    app = _isolated_app()
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import dossier_router

    business_tenant_id = uuid4()
    provider_tenant_id = uuid4()
    dossier_id = uuid4()
    db = FakeConn()
    db.fetchrow_responses = [("FROM dossiers", None)]

    async def fake_resolve_tenant_id(db_arg, user):
        return provider_tenant_id

    monkeypatch.setattr(dossier_router, "_resolve_tenant_id", fake_resolve_tenant_id)
    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "provider", "sub": str(uuid4()), "tenant_id": str(provider_tenant_id)}
    try:
        res = TestClient(app).get(f"/api/dossiers/{dossier_id}/readiness")
    finally:
        app.dependency_overrides.clear()

    assert str(business_tenant_id) != str(provider_tenant_id)
    assert res.status_code == 403
    assert not any(call[0] == "fetch" for call in db.calls)
    assert not any(call[0] == "execute" for call in db.calls)


def test_readiness_route_registered_under_api_prefix(monkeypatch):
    app = _isolated_app()
    from auth.db import get_db
    from auth.jwt_utils import get_current_user
    from auth import dossier_router

    dossier_id = uuid4()
    tenant_id = uuid4()
    standard_id = uuid4()
    db = _base_db(dossier_id=dossier_id, tenant_id=tenant_id, standard_id=standard_id)

    async def fake_resolve_tenant_id(db_arg, user):
        return tenant_id

    monkeypatch.setattr(dossier_router, "_resolve_tenant_id", fake_resolve_tenant_id)
    app.dependency_overrides[get_db] = OverrideDB(db)
    app.dependency_overrides[get_current_user] = lambda: {"role": "business", "sub": str(uuid4()), "tenant_id": str(tenant_id)}
    try:
        res = TestClient(app).get(f"/api/dossiers/{dossier_id}/readiness")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert body["dossier_id"] == str(dossier_id)
    assert body["next_action"] == "upload_required_documents"
async def test_readiness_fails_closed_when_dossier_has_no_published_requirements():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    standard_id = uuid4()
    db = _base_db(dossier_id=dossier_id, tenant_id=tenant_id, standard_id=standard_id)
    dossier = db.fetchrow_responses[0][1]
    dossier["requirements_version_id"] = None
    dossier["requirements_binding_status"] = "unconfigured"

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["state"] == "requirements_unconfigured"
    assert result["readiness_percent"] is None
    assert result["next_action"] == "publish_requirements_version"
    assert result["next_actor_role"] == "platform_admin"
    assert result["blocking_reasons"] == [{"code": "requirements_version_not_published"}]
    assert not _recorded_sql(db, "FROM documents")


async def test_legacy_dossier_without_version_stays_unknown_and_is_not_backfilled():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    db = _base_db(dossier_id=dossier_id, tenant_id=tenant_id, standard_id=uuid4())
    dossier = db.fetchrow_responses[0][1]
    dossier["requirements_version_id"] = None
    dossier["requirements_binding_status"] = "unknown"

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["state"] == "requirements_unknown"
    assert result["readiness_percent"] is None
    assert result["next_action"] == "resolve_requirements_binding"
    assert result["blocking_reasons"] == [{"code": "requirements_version_unknown_no_backfill"}]
    assert not _recorded_sql(db, "FROM standard_requirement_version_slots")


async def test_published_version_with_optional_slots_keeps_them_visible_without_blocking():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id = uuid4()
    tenant_id = uuid4()
    db = _base_db(dossier_id=dossier_id, tenant_id=tenant_id, standard_id=uuid4())
    db.fetch_responses[0] = ("FROM standard_requirement_version_slots", [FakeRecord(doc_type="optional", required=False, display_order=1)])

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["state"] == "requirements_no_required_slots"
    assert result["requirement_slots"] == [{"doc_type": "optional", "required": False, "display_order": 1}]
    assert result["required_documents"] == []
    assert result["missing_required_documents"] == []
    assert result["readiness_percent"] is None
    assert result["blocking_reasons"] == [{"code": "requirements_configured_without_required_slots"}]
    assert not _recorded_sql(db, "FROM documents")



async def test_readiness_includes_state_owner_role_and_earliest_blocking_due_date():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id, tenant_id, standard_id = uuid4(), uuid4(), uuid4()
    db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=_approved_docs(),
        ncrs=[
            FakeRecord(id=uuid4(), status="open", severity="major", description="CAPA due", corrective_action="", deadline=date(2026, 10, 15)),
            FakeRecord(id=uuid4(), status="open", severity="critical", description="Earlier CAPA", corrective_action="", deadline=date(2026, 10, 12)),
        ],
    )

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["state"] == "ncr_open"
    assert result["next_actor_role"] == "business"
    assert result["next_action_owner_role"] == "business"
    assert result["due_date"] == "2026-10-12"
    assert len(result["blocking_ncrs"]) == 2


async def test_minor_ncr_is_visible_but_does_not_block_decision():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id, tenant_id, standard_id = uuid4(), uuid4(), uuid4()
    db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=_approved_docs(),
        ncrs=[FakeRecord(id=uuid4(), status="open", severity="minor", description="Minor note", corrective_action="", deadline=None)],
    )

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["state"] == "ready_for_decision"
    assert result["readiness_percent"] == 75
    assert result["certificate_issue_blocked"] is True
    assert result["next_action"] == "finalize_certification_decision"
    assert len(result["open_ncrs"]) == 1
    assert result["blocking_ncrs"] == []


async def test_approved_decision_without_active_certificate_is_not_reported_certified():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id, tenant_id, standard_id = uuid4(), uuid4(), uuid4()
    db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=_approved_docs(),
        decision=FakeRecord(id=uuid4(), status="approved", decision_reason="Independent approval"),
        cert=None,
    )

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["state"] == "certificate_pending"
    assert result["readiness_percent"] == 75
    assert result["certificate_issue_blocked"] is True
    assert result["safe_public_trace_available"] is False
    assert result["next_action"] == "issue_certificate_artifact"
    assert any(reason["code"] == "active_certificate_missing" for reason in result["blocking_reasons"])


async def test_readiness_requires_certificate_within_validity_window():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id, tenant_id, standard_id = uuid4(), uuid4(), uuid4()
    db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=_approved_docs(),
        decision=FakeRecord(id=uuid4(), status="approved", decision_reason="Independent approval"),
        cert=None,  # expired, future-dated, and inactive rows do not satisfy the DB predicate
    )

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    certificate_queries = _recorded_sql(db, "FROM halal_certificates")
    assert certificate_queries
    certificate_sql = certificate_queries[0][1][0]
    assert "status = 'active'" in certificate_sql
    assert "issue_date <= CURRENT_DATE" in certificate_sql
    assert "expiry_date >= CURRENT_DATE" in certificate_sql
    assert result["state"] == "certificate_pending"
    assert result["safe_public_trace_available"] is False


async def test_legacy_approved_status_does_not_override_current_draft_approval_state():
    from services.dossier_readiness import compute_dossier_readiness

    dossier_id, tenant_id, standard_id = uuid4(), uuid4(), uuid4()
    db = _base_db(
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        standard_id=standard_id,
        docs=[
            FakeRecord(id=uuid4(), doc_type="halal_policy", status="approved", approval_status="draft", compliance_score=99, evaluation_result={}),
            FakeRecord(id=uuid4(), doc_type="has_manual", status="approved", approval_status="approved", compliance_score=99, evaluation_result={}),
        ],
    )

    result = await compute_dossier_readiness(db, dossier_id=str(dossier_id), tenant_id=str(tenant_id))

    assert result["state"] == "documents_in_review"
    assert result["unreviewed_documents"][0]["doc_type"] == "halal_policy"
    assert result["readiness_percent"] == 25


@pytest.mark.parametrize("submitted", [False, True])
async def test_prepared_packet_handoff_changes_only_after_submission(submitted):
    from services.dossier_readiness import compute_dossier_readiness
    dossier_id, tenant_id, standard_id = uuid4(), uuid4(), uuid4()
    docs = [FakeRecord(id=uuid4(), doc_type=kind, status="compliant", approval_status=None, compliance_score=99, evaluation_result={}, version_number=1) for kind in ["halal_policy", "has_manual"]]
    db = _base_db(dossier_id=dossier_id,tenant_id=tenant_id,standard_id=standard_id,docs=docs)
    if not submitted:
        db.fetchrow_responses[1] = ("FROM submissions", None)
    result = await compute_dossier_readiness(db,dossier_id=str(dossier_id),tenant_id=str(tenant_id))
    assert result["readiness_percent"] == 0
    assert result["certificate_issue_blocked"] is True
    assert result["state"] == ("documents_in_review" if submitted else "documents_ready_to_submit")
    assert result["next_action"] == ("review_uploaded_documents" if submitted else "submit_dossier_to_cb")
    assert result["next_actor_role"] == ("reviewer" if submitted else "business")
    assert all(slot["state"] == ("pending_review" if submitted else "ready_to_submit") for slot in result["requirement_slots"])
