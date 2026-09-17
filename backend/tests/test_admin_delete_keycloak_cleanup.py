from pathlib import Path


def _admin_delete_body() -> str:
    src = Path("app.py").read_text()
    start = src.index('def _keycloak_delete_candidates_for_user(row, keycloak_admin) -> list[str]:')
    end = src.index('@app.get("/health")', start)
    return src[start:end]


def test_admin_delete_user_deletes_keycloak_by_sub_and_email_lookup():
    """Admin delete must not leave a stale Keycloak identity owning email.

    Regression: a deleted app user can leave a disabled/live Keycloak account with
    the same email; Keycloak still enforces email uniqueness and blocks re-register.
    The endpoint must therefore delete the stored keycloak_sub and also look up
    the exact email in Keycloak to catch stale/wrong sub rows.
    """
    body = _admin_delete_body()

    assert "_keycloak_delete_candidates_for_user" in body
    assert "candidates.append(str(row[\"keycloak_sub\"]))" in body
    assert "keycloak_admin.find_user_by_email(row[\"email\"])" in body
    assert "keycloak_admin.delete_user(str(kc_sub))" in body


def test_admin_delete_user_fails_closed_when_keycloak_cleanup_fails():
    """Do not delete PG rows if Keycloak cleanup cannot be proven.

    Continuing DB cleanup after Keycloak lookup/delete failure makes the admin UI
    appear successful while the IdP still reserves the email. That is the exact
    class that blocked self-registration for beensand97@gmail.com.
    """
    body = _admin_delete_body()

    assert "Fail closed on Keycloak lookup before deleting any identity" in body
    assert "aborting PG cleanup" in body
    assert "status_code=502" in body
    assert "PG/app DB chưa bị xoá" in body
    assert "partial_keycloak_deleted" in body
    assert "continuing PG cleanup" not in body


def test_admin_delete_business_owner_cleans_child_member_keycloak_accounts_first():
    """Deleting a business owner must not orphan member Keycloak users.

    The PG cleanup deletes tenant members before the owner. The Keycloak cleanup
    must therefore include those member rows before any PG DELETE executes.
    """
    body = _admin_delete_body()

    assert "rows_to_delete = [row]" in body
    assert "SELECT id, role, tenant_id, email, keycloak_sub FROM users WHERE tenant_id=$1 AND id != $1" in body
    assert "rows_to_delete.extend(member_rows)" in body
    assert "_delete_keycloak_identities_for_rows(rows_to_delete, keycloak_admin)" in body


def test_admin_delete_user_documents_stale_sub_registration_conflict_class():
    body = _admin_delete_body()

    assert "stale/wrong keycloak_sub" in body
    assert "blocks future self-registration" in body
    assert "email already registered" in body


def test_admin_keycloak_email_cleanup_endpoint_is_available_for_orphan_identities():
    """Admins need a safe repair path when the app row is already gone.

    Regression: after the PG row is deleted, /admin/users/{id} cannot be called,
    but Keycloak may still reserve the email. The repair endpoint must audit app
    tables first, require explicit confirmation, and only then delete the exact
    Keycloak email match.
    """
    src = Path("app.py").read_text()

    assert "class AdminKeycloakEmailCleanupRequest" in src
    assert '@app.post("/admin/keycloak-identities/cleanup-email")' in src
    assert "_require_admin(request)" in src
    assert "confirm_delete" in src
    assert "_count_app_email_references" in src
    assert "member_invites" in src and "suppliers" in src
    assert "raise HTTPException(409" in src
    assert "keycloak_admin.find_user_by_email(email)" in src
    assert "keycloak_admin.delete_user(kc_sub)" in src
    assert "dry_run" in src
