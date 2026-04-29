"""Feature flag resolver — global defaults + per-tenant overrides + rollout.

Resolution order (first match wins):
  1. Tenant-specific override (force on/off via tenant_feature_overrides)
  2. Rollout percentage (deterministic hash(tenant_id + name) modulo 100)
  3. Global default_enabled

Caching: in-process TTL cache (60s default). Single uvicorn worker is fine
for now; multi-worker would benefit from Redis but not blocking Phase 0.

Resolution is deterministic: same tenant + same flag always returns same
value within a rollout band, so user experience is stable across sessions.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("aminra.feature_flags")

CACHE_TTL_SECONDS = 60.0


@dataclass(frozen=True)
class FlagState:
    name: str
    default_enabled: bool
    rollout_percentage: int
    description: Optional[str] = None


# In-process cache: {(scope, key): (value, expires_at)}
# scope = "global"   key = name   value = FlagState
# scope = "override" key = (tenant_id, name)  value = bool | None
_cache: dict[tuple[str, object], tuple[object, float]] = {}


def _cache_get(scope: str, key: object):
    entry = _cache.get((scope, key))
    if entry is None:
        return None, False
    value, expires_at = entry
    if time.monotonic() > expires_at:
        _cache.pop((scope, key), None)
        return None, False
    return value, True


def _cache_set(scope: str, key: object, value: object, ttl: float = CACHE_TTL_SECONDS) -> None:
    _cache[(scope, key)] = (value, time.monotonic() + ttl)


def invalidate_cache() -> None:
    """Drop entire cache. Call after admin updates a flag/override."""
    _cache.clear()


# ── Hash-based rollout ──────────────────────────────────────────────────────


def _rollout_match(tenant_id: str, feature_name: str, percentage: int) -> bool:
    """Deterministic per-tenant rollout: stable across requests, distributed
    evenly over the tenant population.

    Uses SHA-256 (overkill for this purpose but standard) of "tenant:feature"
    → first 4 bytes → modulo 100. usedforsecurity=False to avoid bandit B324
    even though SHA-256 is fine; signal intent.
    """
    if percentage <= 0:
        return False
    if percentage >= 100:
        return True
    digest = hashlib.sha256(f"{tenant_id}:{feature_name}".encode(), usedforsecurity=False).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    return bucket < percentage


# ── DB lookups (cached) ─────────────────────────────────────────────────────


async def _get_flag(db, name: str) -> Optional[FlagState]:
    cached, hit = _cache_get("global", name)
    if hit:
        return cached  # type: ignore[return-value]
    row = await db.fetchrow(
        "SELECT name, description, default_enabled, rollout_percentage FROM feature_flags WHERE name = $1",
        name,
    )
    if row is None:
        _cache_set("global", name, None)
        return None
    flag = FlagState(
        name=row["name"],
        description=row["description"],
        default_enabled=row["default_enabled"],
        rollout_percentage=row["rollout_percentage"],
    )
    _cache_set("global", name, flag)
    return flag


async def _get_override(db, tenant_id: str, name: str) -> Optional[bool]:
    cached, hit = _cache_get("override", (tenant_id, name))
    if hit:
        return cached  # type: ignore[return-value]
    row = await db.fetchrow(
        "SELECT enabled FROM tenant_feature_overrides WHERE tenant_id = $1 AND feature_name = $2",
        tenant_id,
        name,
    )
    value = row["enabled"] if row else None
    _cache_set("override", (tenant_id, name), value)
    return value


# ── Public API ──────────────────────────────────────────────────────────────


async def is_feature_enabled(db, tenant_id: Optional[str], feature_name: str) -> bool:
    """Resolve feature flag for a tenant. Returns False for unknown flags
    (closed-default policy: missing flag is treated as disabled, not errored —
    callers can guard new code without breaking when the flag isn't seeded yet).
    """
    flag = await _get_flag(db, feature_name)
    if flag is None:
        return False

    # Tenant override takes precedence (only if we have a tenant_id)
    if tenant_id:
        override = await _get_override(db, tenant_id, feature_name)
        if override is not None:
            return override

    # Rollout (requires tenant_id for stable bucketing)
    if tenant_id and flag.rollout_percentage > 0:
        if _rollout_match(tenant_id, feature_name, flag.rollout_percentage):
            return True

    return flag.default_enabled


async def list_flags_for_tenant(db, tenant_id: Optional[str]) -> dict[str, bool]:
    """Resolve EVERY known flag for a tenant. Used by /api/feature-flags/me
    so the frontend can hydrate `useFeature()` lookups from a single fetch.
    """
    rows = await db.fetch("SELECT name, default_enabled, rollout_percentage FROM feature_flags ORDER BY name")
    if not rows:
        return {}

    overrides: dict[str, bool] = {}
    if tenant_id:
        ov_rows = await db.fetch(
            "SELECT feature_name, enabled FROM tenant_feature_overrides WHERE tenant_id = $1",
            tenant_id,
        )
        overrides = {r["feature_name"]: r["enabled"] for r in ov_rows}

    out: dict[str, bool] = {}
    for r in rows:
        name = r["name"]
        if name in overrides:
            out[name] = overrides[name]
            continue
        if tenant_id and r["rollout_percentage"] > 0 and _rollout_match(tenant_id, name, r["rollout_percentage"]):
            out[name] = True
            continue
        out[name] = r["default_enabled"]
    return out


# ── Admin mutations (CRUD) — invalidate cache on every write ────────────────


async def upsert_flag(
    db,
    name: str,
    *,
    description: Optional[str] = None,
    default_enabled: bool = False,
    rollout_percentage: int = 0,
) -> None:
    if not 0 <= rollout_percentage <= 100:
        raise ValueError("rollout_percentage must be between 0 and 100")
    await db.execute(
        """
        INSERT INTO feature_flags (name, description, default_enabled, rollout_percentage)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (name) DO UPDATE SET
          description = EXCLUDED.description,
          default_enabled = EXCLUDED.default_enabled,
          rollout_percentage = EXCLUDED.rollout_percentage,
          updated_at = NOW()
        """,
        name,
        description,
        default_enabled,
        rollout_percentage,
    )
    invalidate_cache()


async def set_tenant_override(
    db,
    tenant_id: str,
    feature_name: str,
    enabled: bool,
    *,
    reason: Optional[str] = None,
    created_by: Optional[str] = None,
) -> None:
    await db.execute(
        """
        INSERT INTO tenant_feature_overrides (tenant_id, feature_name, enabled, override_reason, created_by)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (tenant_id, feature_name) DO UPDATE SET
          enabled = EXCLUDED.enabled,
          override_reason = EXCLUDED.override_reason,
          updated_at = NOW()
        """,
        tenant_id,
        feature_name,
        enabled,
        reason,
        created_by,
    )
    invalidate_cache()


async def clear_tenant_override(db, tenant_id: str, feature_name: str) -> None:
    await db.execute(
        "DELETE FROM tenant_feature_overrides WHERE tenant_id = $1 AND feature_name = $2",
        tenant_id,
        feature_name,
    )
    invalidate_cache()


__all__ = [
    "FlagState",
    "is_feature_enabled",
    "list_flags_for_tenant",
    "upsert_flag",
    "set_tenant_override",
    "clear_tenant_override",
    "invalidate_cache",
    "_rollout_match",
    "CACHE_TTL_SECONDS",
]
