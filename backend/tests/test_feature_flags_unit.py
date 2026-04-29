"""Feature flag — unit tests (Day 6 Phase 0).

Target: ≥50 unit tests covering resolution logic, hash determinism, cache,
mutations. No DB; uses an in-memory fake.
"""

from __future__ import annotations

import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from services import feature_flags
from services.feature_flags import (
    FlagState,
    _rollout_match,
    clear_tenant_override,
    invalidate_cache,
    is_feature_enabled,
    list_flags_for_tenant,
    set_tenant_override,
    upsert_flag,
)

pytestmark = pytest.mark.asyncio


# ── Fake DB ─────────────────────────────────────────────────────────────────


class FakeDB:
    """In-memory stand-in for asyncpg connection. Mirrors fetchrow/fetch/execute."""

    def __init__(self) -> None:
        self.flags: dict[str, dict] = {}
        self.overrides: dict[tuple[str, str], dict] = {}
        self.executed: list[tuple[str, tuple]] = []

    async def fetchrow(self, sql: str, *args):
        sql_lower = sql.lower()
        if "from feature_flags" in sql_lower and "where name" in sql_lower:
            row = self.flags.get(args[0])
            return dict(row) if row else None
        if "from tenant_feature_overrides" in sql_lower:
            return self.overrides.get((args[0], args[1]))
        return None

    async def fetch(self, sql: str, *args):
        sql_lower = sql.lower()
        if "from feature_flags" in sql_lower:
            return [dict(v) for v in self.flags.values()]
        if "from tenant_feature_overrides" in sql_lower and "tenant_id" in sql_lower:
            tenant_id = args[0] if args else None
            return [
                {"feature_name": k[1], "enabled": v["enabled"]}
                for k, v in self.overrides.items()
                if k[0] == tenant_id
            ]
        return []

    async def execute(self, sql: str, *args):
        self.executed.append((sql, args))
        sql_lower = sql.lower()
        if "insert into feature_flags" in sql_lower:
            name, description, default_enabled, rollout = args
            self.flags[name] = {
                "name": name,
                "description": description,
                "default_enabled": default_enabled,
                "rollout_percentage": rollout,
            }
        elif "insert into tenant_feature_overrides" in sql_lower:
            tenant_id, feature_name, enabled, reason, created_by = args
            self.overrides[(tenant_id, feature_name)] = {
                "enabled": enabled,
                "override_reason": reason,
            }
        elif "delete from tenant_feature_overrides" in sql_lower:
            self.overrides.pop((args[0], args[1]), None)


@pytest.fixture(autouse=True)
def _reset_cache():
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def db():
    return FakeDB()


# ── _rollout_match — deterministic hash bucketing (15 cases) ────────────────


class TestRolloutMatch:
    @pytest.mark.parametrize("percentage", [0, -5, -100])
    def test_zero_or_negative_percentage_never_matches(self, percentage):
        assert _rollout_match("any-tenant", "any-flag", percentage) is False

    @pytest.mark.parametrize("percentage", [100, 101, 999])
    def test_percentage_at_or_above_100_always_matches(self, percentage):
        assert _rollout_match("any-tenant", "any-flag", percentage) is True

    def test_same_tenant_same_flag_is_deterministic(self):
        first = _rollout_match("tenant-1", "flag-x", 50)
        for _ in range(20):
            assert _rollout_match("tenant-1", "flag-x", 50) is first

    def test_different_tenants_get_different_buckets(self):
        results = {_rollout_match(f"tenant-{i}", "flag-x", 50) for i in range(200)}
        # Both True and False should appear over 200 samples
        assert results == {True, False}

    def test_different_flags_for_same_tenant_get_different_buckets(self):
        # Tenant pinned, vary flag name → buckets should distribute
        results = {_rollout_match("tenant-1", f"flag-{i}", 50) for i in range(200)}
        assert results == {True, False}

    def test_percentage_50_is_approximately_half(self):
        # 1000 tenants, expect ~500 hits ± 80 (loose to avoid flakiness)
        hits = sum(1 for i in range(1000) if _rollout_match(f"t-{i}", "flag", 50))
        assert 420 <= hits <= 580

    def test_percentage_10_is_approximately_tenth(self):
        hits = sum(1 for i in range(1000) if _rollout_match(f"t-{i}", "flag", 10))
        assert 50 <= hits <= 150

    def test_percentage_90_is_approximately_ninety_percent(self):
        hits = sum(1 for i in range(1000) if _rollout_match(f"t-{i}", "flag", 90))
        assert 850 <= hits <= 950

    def test_hash_uses_tenant_and_flag_name_combined(self):
        # Manual hash → confirm we use exactly "tenant_id:feature_name"
        digest = hashlib.sha256(b"tenant-x:flag-y", usedforsecurity=False).digest()
        bucket = int.from_bytes(digest[:4], "big") % 100
        expected = bucket < 75
        assert _rollout_match("tenant-x", "flag-y", 75) is expected

    def test_unicode_tenant_id_does_not_crash(self):
        # Tenant IDs are uuids in prod but the function shouldn't blow up
        assert isinstance(_rollout_match("tenant-α", "flag-β", 50), bool)


# ── is_feature_enabled — resolution priority (20 cases) ─────────────────────


class TestIsFeatureEnabled:
    async def test_unknown_flag_returns_false(self, db):
        assert await is_feature_enabled(db, "tenant-1", "missing") is False

    async def test_default_disabled_no_rollout_returns_false(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=0)
        assert await is_feature_enabled(db, "tenant-1", "f1") is False

    async def test_default_enabled_no_rollout_returns_true(self, db):
        await upsert_flag(db, "f1", default_enabled=True, rollout_percentage=0)
        assert await is_feature_enabled(db, "tenant-1", "f1") is True

    async def test_full_rollout_returns_true_regardless_of_default(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=100)
        assert await is_feature_enabled(db, "tenant-1", "f1") is True

    async def test_zero_rollout_falls_through_to_default(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=0)
        assert await is_feature_enabled(db, "tenant-1", "f1") is False

    async def test_override_true_beats_disabled_default(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=0)
        await set_tenant_override(db, "tenant-1", "f1", True)
        assert await is_feature_enabled(db, "tenant-1", "f1") is True

    async def test_override_false_beats_enabled_default(self, db):
        await upsert_flag(db, "f1", default_enabled=True, rollout_percentage=0)
        await set_tenant_override(db, "tenant-1", "f1", False)
        assert await is_feature_enabled(db, "tenant-1", "f1") is False

    async def test_override_false_beats_full_rollout(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=100)
        await set_tenant_override(db, "tenant-1", "f1", False)
        assert await is_feature_enabled(db, "tenant-1", "f1") is False

    async def test_override_for_one_tenant_does_not_affect_another(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=0)
        await set_tenant_override(db, "tenant-A", "f1", True)
        assert await is_feature_enabled(db, "tenant-A", "f1") is True
        assert await is_feature_enabled(db, "tenant-B", "f1") is False

    async def test_no_tenant_id_skips_override(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=0)
        # Should fall through to default without crashing
        assert await is_feature_enabled(db, None, "f1") is False

    async def test_no_tenant_id_skips_rollout(self, db):
        # Rollout requires tenant_id for stable bucketing; no tenant → use default
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=100)
        assert await is_feature_enabled(db, None, "f1") is False

    async def test_no_tenant_id_returns_default_true(self, db):
        await upsert_flag(db, "f1", default_enabled=True, rollout_percentage=0)
        assert await is_feature_enabled(db, None, "f1") is True

    async def test_clear_override_falls_back_to_default(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=0)
        await set_tenant_override(db, "tenant-1", "f1", True)
        await clear_tenant_override(db, "tenant-1", "f1")
        assert await is_feature_enabled(db, "tenant-1", "f1") is False

    async def test_upsert_overwrites_existing(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=0)
        await upsert_flag(db, "f1", default_enabled=True, rollout_percentage=0)
        assert await is_feature_enabled(db, "tenant-1", "f1") is True

    async def test_invalid_rollout_percentage_raises(self, db):
        with pytest.raises(ValueError):
            await upsert_flag(db, "f1", rollout_percentage=101)
        with pytest.raises(ValueError):
            await upsert_flag(db, "f1", rollout_percentage=-1)

    async def test_partial_rollout_is_consistent_per_tenant(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=50)
        # A tenant gets the same answer twice in a row
        first = await is_feature_enabled(db, "tenant-1", "f1")
        invalidate_cache()  # bust cache to force re-resolve
        second = await is_feature_enabled(db, "tenant-1", "f1")
        assert first == second

    async def test_partial_rollout_distributes_across_tenants(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=50)
        results = []
        for i in range(50):
            invalidate_cache()
            results.append(await is_feature_enabled(db, f"tenant-{i}", "f1"))
        # Both True and False should appear
        assert True in results and False in results

    async def test_empty_string_tenant_treated_as_no_tenant(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=100)
        # Falsy tenant_id ("" → bool False) skips override + rollout
        assert await is_feature_enabled(db, "", "f1") is False

    async def test_override_for_wrong_flag_does_not_leak(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        await upsert_flag(db, "f2", default_enabled=False)
        await set_tenant_override(db, "tenant-1", "f1", True)
        assert await is_feature_enabled(db, "tenant-1", "f1") is True
        assert await is_feature_enabled(db, "tenant-1", "f2") is False

    async def test_default_enabled_with_partial_rollout_returns_true(self, db):
        # If default is enabled, rollout doesn't matter for tenants outside band
        # (they still get default=True via the final fallback)
        await upsert_flag(db, "f1", default_enabled=True, rollout_percentage=10)
        results = [await is_feature_enabled(db, f"t-{i}", "f1") for i in range(20)]
        # All should be True (either via rollout or default)
        assert all(results)


# ── list_flags_for_tenant — bulk resolution (10 cases) ──────────────────────


class TestListFlagsForTenant:
    async def test_empty_returns_empty_dict(self, db):
        result = await list_flags_for_tenant(db, "tenant-1")
        assert result == {}

    async def test_single_flag_default_disabled(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        assert await list_flags_for_tenant(db, "tenant-1") == {"f1": False}

    async def test_single_flag_default_enabled(self, db):
        await upsert_flag(db, "f1", default_enabled=True)
        assert await list_flags_for_tenant(db, "tenant-1") == {"f1": True}

    async def test_multiple_flags(self, db):
        await upsert_flag(db, "f1", default_enabled=True)
        await upsert_flag(db, "f2", default_enabled=False)
        await upsert_flag(db, "f3", default_enabled=True)
        result = await list_flags_for_tenant(db, "tenant-1")
        assert result == {"f1": True, "f2": False, "f3": True}

    async def test_override_takes_precedence(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        await set_tenant_override(db, "tenant-1", "f1", True)
        assert await list_flags_for_tenant(db, "tenant-1") == {"f1": True}

    async def test_override_per_tenant_isolation(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        await set_tenant_override(db, "tenant-A", "f1", True)
        assert await list_flags_for_tenant(db, "tenant-A") == {"f1": True}
        assert await list_flags_for_tenant(db, "tenant-B") == {"f1": False}

    async def test_full_rollout_applies(self, db):
        await upsert_flag(db, "f1", default_enabled=False, rollout_percentage=100)
        assert (await list_flags_for_tenant(db, "tenant-1"))["f1"] is True

    async def test_no_tenant_returns_defaults(self, db):
        await upsert_flag(db, "f1", default_enabled=True)
        await upsert_flag(db, "f2", default_enabled=False)
        result = await list_flags_for_tenant(db, None)
        assert result == {"f1": True, "f2": False}

    async def test_mixed_overrides_and_defaults(self, db):
        await upsert_flag(db, "ihc_meetings_v1", default_enabled=False)
        await upsert_flag(db, "training_matrix_v1", default_enabled=False)
        await upsert_flag(db, "ccp_table_v1", default_enabled=True)
        await set_tenant_override(db, "tenant-1", "ihc_meetings_v1", True)
        await set_tenant_override(db, "tenant-1", "ccp_table_v1", False)
        result = await list_flags_for_tenant(db, "tenant-1")
        assert result == {
            "ihc_meetings_v1": True,
            "training_matrix_v1": False,
            "ccp_table_v1": False,
        }

    async def test_clear_override_falls_back(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        await set_tenant_override(db, "tenant-1", "f1", True)
        await clear_tenant_override(db, "tenant-1", "f1")
        assert (await list_flags_for_tenant(db, "tenant-1"))["f1"] is False


# ── Cache behavior (8 cases) ────────────────────────────────────────────────


class TestCache:
    async def test_global_flag_lookup_is_cached(self, db):
        await upsert_flag(db, "f1", default_enabled=True)
        await is_feature_enabled(db, "tenant-1", "f1")
        # Subsequent call should not hit DB again — track calls via patching
        original_fetchrow = db.fetchrow
        call_count = 0

        async def counting(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return await original_fetchrow(*args, **kwargs)

        db.fetchrow = counting
        await is_feature_enabled(db, "tenant-1", "f1")
        # Should hit DB only for override lookup, not the global flag
        # (global lookup is cached after first call)
        assert call_count <= 1  # Only override fetch, not flag fetch

    async def test_invalidate_cache_clears_global(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        # Cache the result
        await is_feature_enabled(db, "tenant-1", "f1")
        # Mutate via direct DB write that bypasses our wrapper
        db.flags["f1"]["default_enabled"] = True
        # Without cache invalidation, stale value is returned
        assert await is_feature_enabled(db, "tenant-1", "f1") is False
        # After invalidation, fresh lookup
        invalidate_cache()
        assert await is_feature_enabled(db, "tenant-1", "f1") is True

    async def test_upsert_invalidates_cache_automatically(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        await is_feature_enabled(db, "tenant-1", "f1")
        await upsert_flag(db, "f1", default_enabled=True)
        assert await is_feature_enabled(db, "tenant-1", "f1") is True

    async def test_set_override_invalidates_cache_automatically(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        await is_feature_enabled(db, "tenant-1", "f1")
        await set_tenant_override(db, "tenant-1", "f1", True)
        assert await is_feature_enabled(db, "tenant-1", "f1") is True

    async def test_clear_override_invalidates_cache_automatically(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        await set_tenant_override(db, "tenant-1", "f1", True)
        await is_feature_enabled(db, "tenant-1", "f1")
        await clear_tenant_override(db, "tenant-1", "f1")
        assert await is_feature_enabled(db, "tenant-1", "f1") is False

    async def test_negative_cache_for_unknown_flag(self, db):
        # First call records a None in cache
        assert await is_feature_enabled(db, "tenant-1", "nonexistent") is False
        # Now define the flag (bypass our writer to keep cache stale)
        db.flags["nonexistent"] = {
            "name": "nonexistent",
            "description": None,
            "default_enabled": True,
            "rollout_percentage": 0,
        }
        # Stale cache returns False
        assert await is_feature_enabled(db, "tenant-1", "nonexistent") is False
        # After invalidation, fresh
        invalidate_cache()
        assert await is_feature_enabled(db, "tenant-1", "nonexistent") is True

    async def test_cache_is_independent_per_tenant_for_overrides(self, db):
        await upsert_flag(db, "f1", default_enabled=False)
        await set_tenant_override(db, "tenant-A", "f1", True)
        # First call for A caches override=True
        assert await is_feature_enabled(db, "tenant-A", "f1") is True
        # Tenant B has no override → cache miss for B → fetches None → caches None
        assert await is_feature_enabled(db, "tenant-B", "f1") is False

    async def test_cache_ttl_constant_is_reasonable(self):
        # Don't allow regression to 0 or huge values silently
        assert 5 <= feature_flags.CACHE_TTL_SECONDS <= 600


# ── Error/edge cases (5 cases) ──────────────────────────────────────────────


class TestEdgeCases:
    async def test_upsert_with_default_args(self, db):
        await upsert_flag(db, "f1")
        flag = db.flags["f1"]
        assert flag["default_enabled"] is False
        assert flag["rollout_percentage"] == 0

    async def test_upsert_with_description_persists(self, db):
        await upsert_flag(db, "f1", description="test desc")
        assert db.flags["f1"]["description"] == "test desc"

    async def test_set_override_with_reason_persists(self, db):
        await upsert_flag(db, "f1")
        await set_tenant_override(db, "tenant-1", "f1", True, reason="EU pilot")
        assert db.overrides[("tenant-1", "f1")]["override_reason"] == "EU pilot"

    async def test_clear_nonexistent_override_no_error(self, db):
        # Should not raise even if override doesn't exist
        await clear_tenant_override(db, "tenant-1", "f1")
        assert ("tenant-1", "f1") not in db.overrides

    async def test_flagstate_dataclass_is_frozen(self):
        flag = FlagState(name="f1", default_enabled=True, rollout_percentage=50)
        with pytest.raises((AttributeError, Exception)):
            flag.name = "mutated"  # frozen dataclass

    async def test_repeated_upserts_are_idempotent(self, db):
        for _ in range(10):
            await upsert_flag(db, "f1", default_enabled=True, rollout_percentage=25)
        assert db.flags["f1"]["default_enabled"] is True
        assert db.flags["f1"]["rollout_percentage"] == 25
