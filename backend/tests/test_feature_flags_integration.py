"""Feature flag — integration tests (Day 6 Phase 0).

Target: ≥20 integration tests against the live backend (router → service →
real DB roundtrip). Skips cleanly when backend is not reachable.

Requires:
- Backend running with migration 016_feature_flags applied
- TEST_ADMIN_EMAIL + TEST_ADMIN_PASSWORD env for admin endpoints
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.integration


def _backend_unreachable(client) -> bool:
    try:
        r = client.get("/health")
        return r.status_code != 200
    except Exception:
        return True


# ── Tenant-facing /api/feature-flags/me ─────────────────────────────────────


class TestMyFeatureFlags:
    def test_unauthenticated_request_blocked(self, client):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        r = client.get("/api/feature-flags/me")
        assert r.status_code in (401, 403)

    def test_with_admin_token_returns_flag_dict(self, client, admin_token):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        r = client.get("/api/feature-flags/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        body = r.json()
        assert "flags" in body
        assert isinstance(body["flags"], dict)

    def test_response_includes_tenant_id_field(self, client, admin_token):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        r = client.get("/api/feature-flags/me", headers={"Authorization": f"Bearer {admin_token}"})
        body = r.json()
        assert "tenant_id" in body  # may be None for admin

    def test_seeded_tier1_flags_present(self, client, admin_token):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        r = client.get("/api/feature-flags/me", headers={"Authorization": f"Bearer {admin_token}"})
        flags = r.json()["flags"]
        for tier1 in ("ihc_meetings_v1", "training_matrix_v1", "internal_audit_v1"):
            assert tier1 in flags, f"Tier-1 flag {tier1} missing — migration 016 applied?"

    def test_seeded_flags_default_disabled(self, client, admin_token):
        """Tier-1 flags ship dark per migration 016 seed."""
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        r = client.get("/api/feature-flags/me", headers={"Authorization": f"Bearer {admin_token}"})
        flags = r.json()["flags"]
        # All Tier-1 flags should be False by default
        tier1_keys = [k for k in flags if k.endswith("_v1")]
        assert len(tier1_keys) >= 5
        # Admin has no tenant_id → default applies → all False
        for key in tier1_keys:
            assert flags[key] is False, f"Expected {key} to default to False"


# ── Admin CRUD on flags ─────────────────────────────────────────────────────


class TestAdminFlagCRUD:
    def test_admin_list_returns_flags_and_overrides(self, client, admin_token):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        r = client.get("/auth/admin/feature-flags", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        body = r.json()
        assert "flags" in body
        assert "overrides" in body
        assert isinstance(body["flags"], list)
        assert isinstance(body["overrides"], list)

    def test_non_admin_cannot_list_admin_flags(self, client):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        # No token → 401
        r = client.get("/auth/admin/feature-flags")
        assert r.status_code in (401, 403)

    def test_upsert_new_flag(self, client, admin_token):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        name = f"test_flag_{uuid.uuid4().hex[:8]}"
        r = client.put(
            f"/auth/admin/feature-flags/{name}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"description": "integration test", "default_enabled": True, "rollout_percentage": 50},
        )
        assert r.status_code == 200
        assert r.json()["name"] == name

    def test_upsert_with_invalid_rollout_returns_422(self, client, admin_token):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        r = client.put(
            "/auth/admin/feature-flags/test_invalid_rollout",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"rollout_percentage": 150},
        )
        assert r.status_code in (400, 422)

    def test_upsert_with_negative_rollout_returns_422(self, client, admin_token):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        r = client.put(
            "/auth/admin/feature-flags/test_neg_rollout",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"rollout_percentage": -10},
        )
        assert r.status_code in (400, 422)

    def test_upsert_persists_across_get(self, client, admin_token):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        if not admin_token:
            pytest.skip("admin_token fixture unavailable")
        name = f"test_persist_{uuid.uuid4().hex[:8]}"
        client.put(
            f"/auth/admin/feature-flags/{name}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"default_enabled": True, "rollout_percentage": 0},
        )
        r = client.get("/auth/admin/feature-flags", headers={"Authorization": f"Bearer {admin_token}"})
        flags = r.json()["flags"]
        match = [f for f in flags if f["name"] == name]
        assert len(match) == 1
        assert match[0]["default_enabled"] is True


# ── Admin CRUD on overrides ─────────────────────────────────────────────────


class TestAdminOverrides:
    @pytest.fixture
    def setup_flag(self, client, admin_token):
        if _backend_unreachable(client) or not admin_token:
            pytest.skip("Backend not reachable")
        name = f"override_test_{uuid.uuid4().hex[:8]}"
        client.put(
            f"/auth/admin/feature-flags/{name}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"default_enabled": False, "rollout_percentage": 0},
        )
        return name

    def test_set_override_for_tenant(self, client, admin_token, setup_flag):
        tenant_id = str(uuid.uuid4())
        r = client.put(
            f"/auth/admin/feature-flags/{setup_flag}/overrides/{tenant_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"enabled": True, "reason": "pilot"},
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is True

    def test_set_override_for_unknown_flag_returns_404(self, client, admin_token):
        if _backend_unreachable(client) or not admin_token:
            pytest.skip("Backend not reachable")
        tenant_id = str(uuid.uuid4())
        r = client.put(
            f"/auth/admin/feature-flags/never_exists_{uuid.uuid4().hex[:8]}/overrides/{tenant_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"enabled": True},
        )
        assert r.status_code == 404

    def test_set_override_then_clear(self, client, admin_token, setup_flag):
        tenant_id = str(uuid.uuid4())
        client.put(
            f"/auth/admin/feature-flags/{setup_flag}/overrides/{tenant_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"enabled": True},
        )
        r = client.delete(
            f"/auth/admin/feature-flags/{setup_flag}/overrides/{tenant_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200

    def test_override_appears_in_admin_list(self, client, admin_token, setup_flag):
        tenant_id = str(uuid.uuid4())
        client.put(
            f"/auth/admin/feature-flags/{setup_flag}/overrides/{tenant_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"enabled": True, "reason": "for visibility"},
        )
        r = client.get("/auth/admin/feature-flags", headers={"Authorization": f"Bearer {admin_token}"})
        overrides = r.json()["overrides"]
        match = [o for o in overrides if o["feature_name"] == setup_flag and str(o["tenant_id"]) == tenant_id]
        assert len(match) == 1
        assert match[0]["enabled"] is True

    def test_override_idempotent_upsert(self, client, admin_token, setup_flag):
        tenant_id = str(uuid.uuid4())
        for enabled in (True, False, True):
            r = client.put(
                f"/auth/admin/feature-flags/{setup_flag}/overrides/{tenant_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"enabled": enabled},
            )
            assert r.status_code == 200
            assert r.json()["enabled"] is enabled


# ── Tenant isolation (security/multi-tenant) ────────────────────────────────


class TestTenantIsolation:
    def test_unauth_admin_endpoints_blocked(self, client):
        if _backend_unreachable(client):
            pytest.skip("Backend not reachable")
        for method, path in (
            ("get", "/auth/admin/feature-flags"),
            ("put", "/auth/admin/feature-flags/x"),
            ("put", "/auth/admin/feature-flags/x/overrides/y"),
            ("delete", "/auth/admin/feature-flags/x/overrides/y"),
        ):
            r = getattr(client, method)(path, json={} if method == "put" else None)
            assert r.status_code in (401, 403), f"{method.upper()} {path} should be blocked, got {r.status_code}"

    def test_my_endpoint_does_not_leak_other_tenant_overrides(self, client, admin_token):
        """Set an override for tenant-X and verify GET /me as admin (no tenant)
        does NOT include that tenant's specific value — only globals.
        """
        if _backend_unreachable(client) or not admin_token:
            pytest.skip("Backend not reachable")
        flag = f"isolation_test_{uuid.uuid4().hex[:8]}"
        client.put(
            f"/auth/admin/feature-flags/{flag}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"default_enabled": False},
        )
        other_tenant = str(uuid.uuid4())
        client.put(
            f"/auth/admin/feature-flags/{flag}/overrides/{other_tenant}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"enabled": True},
        )
        # Admin (no tenant_id) reading their own flags should see flag=False (default)
        r = client.get("/api/feature-flags/me", headers={"Authorization": f"Bearer {admin_token}"})
        flags = r.json()["flags"]
        if flag in flags:
            # Admin tenant_id is None → override doesn't apply → default False
            assert flags[flag] is False
