from pathlib import Path


def _src() -> str:
    return Path("app.py").read_text()


def _function_block(src: str, function_name: str) -> str:
    start = src.index(f"async def {function_name}")
    next_route = src.find("\n\n@app.", start + 1)
    return src[start:next_route if next_route != -1 else len(src)]


def test_admin_delete_user_endpoint_is_deprecated_in_favor_of_keycloak():
    """AMINRA Admin must not be a second account-deletion authority."""
    src = _src()
    body = _function_block(src, "admin_delete_user")

    guard_pos = body.index("_raise_keycloak_only_account_management()")
    assert "_require_admin(request)" in body[:guard_pos]
    assert "keycloak_admin." not in body
    assert "DELETE FROM users" not in body
    assert '"identity_lifecycle_owner": "keycloak"' in src


def test_admin_keycloak_email_cleanup_endpoint_is_deprecated_in_favor_of_keycloak():
    """Identity repair must happen in Keycloak, not via AMINRA Admin repair CRUD."""
    src = _src()
    body = _function_block(src, "admin_cleanup_keycloak_identity_by_email")

    guard_pos = body.index("_raise_keycloak_only_account_management()")
    assert "_require_admin(request)" in body[:guard_pos]
    assert "keycloak_admin." not in body
    assert "confirm_delete" not in body
    assert "_count_app_email_references" not in src
    assert '"identity_lifecycle_owner": "keycloak"' in src


def test_legacy_keycloak_cleanup_helpers_are_removed_from_admin_app():
    src = _src()
    assert "def _keycloak_delete_candidates_for_user" not in src
    assert "def _delete_keycloak_identities_for_rows" not in src
    assert "def _normalise_cleanup_email" not in src
