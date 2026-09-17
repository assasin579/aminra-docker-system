from pathlib import Path


def test_admin_delete_user_deletes_keycloak_by_sub_and_email_lookup():
    """Admin delete must not leave a disabled/stale Keycloak identity owning email.

    Regression: a deleted app user can leave a disabled Keycloak account with the
    same email; Keycloak still enforces email uniqueness and blocks re-register.
    The endpoint must therefore delete the stored keycloak_sub and also look up
    the exact email in Keycloak to catch stale/wrong sub rows.
    """
    src = Path("app.py").read_text()
    start = src.index('async def admin_delete_user(user_id: str, request: Request):')
    end = src.index('@app.get("/health")', start)
    body = src[start:end]

    assert "kc_candidates" in body
    assert "keycloak_admin.find_user_by_email(row[\"email\"])" in body
    assert "for kc_sub in kc_candidates" in body
    assert "keycloak_admin.delete_user(str(kc_sub))" in body


def test_admin_delete_user_documents_stale_sub_registration_conflict_class():
    src = Path("app.py").read_text()
    start = src.index('async def admin_delete_user(user_id: str, request: Request):')
    end = src.index('@app.get("/health")', start)
    body = src[start:end]

    assert "stale/wrong keycloak_sub" in body
    assert "blocks future self-registration" in body
