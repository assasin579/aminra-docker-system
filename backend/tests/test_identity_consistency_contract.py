from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_document_approval_writes_canonical_app_user_id_not_keycloak_sub():
    src = (ROOT / "auth" / "document_router.py").read_text()
    marker = "UPDATE documents\n               SET approval_status      = 'approved'"
    start = src.index(marker)
    block = src[start : src.index("await _audit_strict", start)]

    assert "approver_id = await resolve_canonical_user_id(user, db)" in src
    assert 'user.get("sub")' not in block
    assert 'user["sub"]' not in block


def test_auth_me_uses_identity_reconciliation_gate():
    src = (ROOT / "auth" / "router.py").read_text()
    start = src.index('@router.get("/me", response_model=UserProfile)')
    block = src[start : src.index("# ── Invite member", start)]

    assert "get_or_reconcile_user_from_keycloak_claims(user, db)" in block
    assert 'WHERE keycloak_sub' not in block
    assert 'WHERE id = $1", user["sub"]' not in block
