from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
SYNC_SCRIPT = ROOT / "scripts" / "keycloak_db_projection_sync.py"


def _app_source() -> str:
    return APP_FILE.read_text(encoding="utf-8")


def _function_block(src: str, function_name: str) -> str:
    start = src.index(f"async def {function_name}")
    next_fn = src.find("\nasync def ", start + 1)
    if next_fn == -1:
        next_fn = src.find("\ndef ", start + 1)
    return src[start:next_fn if next_fn != -1 else len(src)]


def test_admin_account_identity_mutation_endpoints_are_deprecated_keycloak_only():
    """Platform Admin must not be a second source of truth for accounts.

    Account/user lifecycle belongs in Keycloak only. AMINRA Admin may inspect
    local profile projections, but it must not create/delete/update account
    identities, reset credentials, or run Keycloak cleanup repair from the app.
    """
    src = _app_source()

    assert "KEYCLOAK_ONLY_ACCOUNT_MANAGEMENT_DETAIL" in src
    assert '"identity_lifecycle_owner": "keycloak"' in src

    for function_name in [
        "admin_create_user",
        "admin_reset_user_password",
        "admin_update_user",
        "admin_cleanup_keycloak_identity_by_email",
        "admin_delete_user",
    ]:
        body = _function_block(src, function_name)
        guard_pos = body.index("_raise_keycloak_only_account_management()")
        assert "_require_admin(request)" in body[:guard_pos], function_name
        assert "from auth.db import get_pool" not in body[:guard_pos], function_name
        assert "keycloak_admin." not in body[:guard_pos], function_name


def test_admin_user_list_is_read_only_projection_with_keycloak_reference():
    src = _app_source()

    list_body = _function_block(src, "admin_list_users")
    assert "keycloak_sub" in list_body
    assert "identity_source" in list_body
    assert "identity_status" in list_body
    assert "keycloak_deleted_at" in list_body
    assert "UPDATE users" not in list_body
    assert "DELETE FROM users" not in list_body
    assert "keycloak_admin." not in list_body


def test_admin_delete_impact_endpoint_is_read_only_preflight():
    src = _app_source()

    assert '@app.get("/admin/users/{user_id}/delete-impact")' in src
    body = _function_block(src, "admin_user_delete_impact")
    assert "_require_admin(request)" in body
    assert "deletion_warnings" in body
    assert "recommended_action" in body
    assert "hard_delete_safe" in body
    assert "DELETE FROM users" not in body
    assert "UPDATE users" not in body
    assert "keycloak_admin.delete" not in body


def test_keycloak_projection_sync_script_is_mark_only_not_destructive():
    text = SYNC_SCRIPT.read_text(encoding="utf-8")

    assert "--apply" in text
    assert "identity_status" in text
    assert "missing_in_keycloak" in text
    assert "keycloak_deleted_at" in text
    assert "DELETE FROM users" not in text
    assert "keycloak_admin.delete" not in text
    assert ".delete(" not in text
