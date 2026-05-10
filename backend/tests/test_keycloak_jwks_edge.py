"""JWKs cache edge cases (Tier 2 E2E batch 2).

Scenarios from operator perspective: Keycloak rolls keys, JWKs endpoint
goes flaky, network partitions, malformed responses, simultaneous
requests during refresh. Each test names the operational situation.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import httpx
import pytest

from auth import keycloak_validator as kv


@pytest.fixture(autouse=True)
def _reset_jwks():
    kv._jwks_cache["keys"] = None
    kv._jwks_cache["fetched_at"] = 0.0
    yield
    kv._jwks_cache["keys"] = None
    kv._jwks_cache["fetched_at"] = 0.0


def _resp(json_body: dict | None = None, status_code: int = 200, raise_on_status: bool = False):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body or {}
    if raise_on_status:
        def _raise():
            raise httpx.HTTPStatusError("err", request=MagicMock(), response=r)
        r.raise_for_status = _raise
    else:
        r.raise_for_status = lambda: None
    return r


# ── 1. Cache lifecycle basics ────────────────────────────────────────────────


def test_first_call_populates_cache(monkeypatch):
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({"keys": [{"kid": "k1"}]}),
    )
    kv._fetch_jwks()
    assert kv._jwks_cache["keys"] == [{"kid": "k1"}]
    assert kv._jwks_cache["fetched_at"] > 0


def test_cache_serves_subsequent_calls_within_ttl(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        return _resp({"keys": [{"kid": "k1"}]})

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    for _ in range(50):
        kv._fetch_jwks()
    assert calls["n"] == 1


def test_cache_expiry_at_exact_ttl_boundary(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        return _resp({"keys": [{"kid": f"k{calls['n']}"}]})

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    kv._fetch_jwks()
    # Set fetched_at exactly to TTL boundary - should not refetch yet
    kv._jwks_cache["fetched_at"] = time.time() - kv._JWKS_TTL + 0.5
    kv._fetch_jwks()
    # Set 1 second past expiry - should refetch
    kv._jwks_cache["fetched_at"] = time.time() - kv._JWKS_TTL - 1
    kv._fetch_jwks()
    assert calls["n"] == 2


def test_force_refetch_bypasses_ttl(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        return _resp({"keys": []})

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    kv._fetch_jwks()
    kv._fetch_jwks(force=True)
    kv._fetch_jwks(force=True)
    assert calls["n"] == 3


def test_cache_keys_field_returned_directly(monkeypatch):
    sample = [{"kid": "k1", "kty": "RSA", "n": "x", "e": "AQAB"}]
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({"keys": sample}),
    )
    out = kv._fetch_jwks()
    assert out is kv._jwks_cache["keys"]


# ── 2. Network failure modes ─────────────────────────────────────────────────


def test_network_timeout_propagates(monkeypatch):
    def raise_timeout(*a, **kw):
        raise httpx.ConnectTimeout("conn timeout")
    monkeypatch.setattr(kv.httpx, "get", raise_timeout)
    with pytest.raises(httpx.ConnectTimeout):
        kv._fetch_jwks()
    # Cache not populated
    assert kv._jwks_cache["keys"] is None


def test_dns_failure_propagates(monkeypatch):
    def raise_dns(*a, **kw):
        raise httpx.ConnectError("dns fail")
    monkeypatch.setattr(kv.httpx, "get", raise_dns)
    with pytest.raises(httpx.ConnectError):
        kv._fetch_jwks()


def test_5xx_response_raises(monkeypatch):
    def get_503(*a, **kw):
        return _resp(status_code=503, raise_on_status=True)
    monkeypatch.setattr(kv.httpx, "get", get_503)
    with pytest.raises(httpx.HTTPStatusError):
        kv._fetch_jwks()


def test_4xx_response_raises(monkeypatch):
    def get_403(*a, **kw):
        return _resp(status_code=403, raise_on_status=True)
    monkeypatch.setattr(kv.httpx, "get", get_403)
    with pytest.raises(httpx.HTTPStatusError):
        kv._fetch_jwks()


def test_failure_after_warm_cache_does_not_evict(monkeypatch):
    """If JWKs endpoint goes down AFTER initial warmup, cached keys stay
    useful within TTL — operational availability."""
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({"keys": [{"kid": "warm"}]}),
    )
    kv._fetch_jwks()
    assert kv._jwks_cache["keys"] == [{"kid": "warm"}]

    # Endpoint goes down, but cache still warm
    def fail(*a, **kw): raise httpx.ConnectError("down")
    monkeypatch.setattr(kv.httpx, "get", fail)
    out = kv._fetch_jwks()  # within TTL — uses cache, no fetch
    assert out == [{"kid": "warm"}]


# ── 3. Malformed JWKs response shapes ────────────────────────────────────────


def test_response_with_no_keys_field(monkeypatch):
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({}),  # missing 'keys'
    )
    out = kv._fetch_jwks()
    assert out == []


def test_response_with_empty_keys_array(monkeypatch):
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({"keys": []}),
    )
    out = kv._fetch_jwks()
    assert out == []


def test_response_with_keys_as_string(monkeypatch):
    """Keycloak misconfigured / proxy mangled — keys is a string."""
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({"keys": "not-a-list"}),
    )
    out = kv._fetch_jwks()
    # Returns whatever .get('keys', []) yields. Downstream lookup will fail.
    assert out == "not-a-list"


def test_response_with_extra_fields_ignored(monkeypatch):
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({
            "keys": [{"kid": "k1"}],
            "metadata": "ignored",
            "issuer": "anything",
        }),
    )
    out = kv._fetch_jwks()
    assert out == [{"kid": "k1"}]


# ── 4. Key lookup edge cases ─────────────────────────────────────────────────


def test_key_for_kid_returns_first_match(monkeypatch):
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({"keys": [
            {"kid": "k1", "kty": "RSA"},
            {"kid": "k2", "kty": "RSA"},
            {"kid": "k1", "kty": "EC"},   # dup kid different kty
        ]}),
    )
    found = kv._key_for_kid("k1")
    assert found is not None
    assert found["kty"] == "RSA"  # first match


def test_key_for_kid_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({"keys": [{"kid": "k1"}]}),
    )
    assert kv._key_for_kid("nonexistent") is None


def test_unknown_kid_triggers_force_refresh(monkeypatch):
    """Key rotation just happened: token has new kid not in current cache.
    Validator must do a force-refresh once before declaring 'unknown'."""
    state = {"call": 0, "served": [{"kid": "old"}]}

    def fake_get(*a, **kw):
        state["call"] += 1
        if state["call"] == 1:
            return _resp({"keys": [{"kid": "old"}]})
        # On forced second call, serve rotated keys
        return _resp({"keys": [{"kid": "old"}, {"kid": "new"}]})

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    found = kv._key_for_kid("new")
    assert found == {"kid": "new"}
    assert state["call"] == 2  # initial + force refresh


def test_unknown_kid_after_force_refresh_returns_none(monkeypatch):
    """Even after force-refresh, kid still not present → give up."""
    monkeypatch.setattr(
        kv.httpx, "get",
        lambda *a, **kw: _resp({"keys": [{"kid": "only-one"}]}),
    )
    assert kv._key_for_kid("never-existed") is None


def test_force_refresh_disabled_returns_none_immediately(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        return _resp({"keys": [{"kid": "k1"}]})

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    kv._fetch_jwks()  # warm cache: 1 call
    out = kv._key_for_kid("missing", allow_refresh=False)
    assert out is None
    # Should not have triggered a 2nd fetch
    assert calls["n"] == 1


# ── 5. Concurrency ───────────────────────────────────────────────────────────


def test_concurrent_threads_only_fetch_once(monkeypatch):
    """Lock serialises the first fetch — 10 threads racing only call
    httpx.get once, the rest see warm cache."""
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        time.sleep(0.05)  # widen the race window
        return _resp({"keys": [{"kid": "k1"}]})

    monkeypatch.setattr(kv.httpx, "get", fake_get)

    threads = [threading.Thread(target=kv._fetch_jwks) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert calls["n"] == 1


def test_concurrent_force_refreshes_serialise(monkeypatch):
    """Multiple force=True calls don't pile up fetches sequentially —
    they each go through. Document the (current) behaviour: force
    re-enters the fetch logic regardless of warm cache."""
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        return _resp({"keys": []})

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    threads = [threading.Thread(target=lambda: kv._fetch_jwks(force=True))
               for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert calls["n"] == 5  # force always fetches


# ── 6. Configuration drift ───────────────────────────────────────────────────


def test_jwks_url_constructed_from_env(monkeypatch):
    """Validate the URL we hit is the canonical Keycloak JWKs path."""
    captured = {}

    def fake_get(url, *a, **kw):
        captured["url"] = url
        return _resp({"keys": []})

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    kv._fetch_jwks()
    assert captured["url"].endswith(
        f"/realms/{kv.KEYCLOAK_REALM}/protocol/openid-connect/certs",
    )


def test_jwks_fetch_timeout_is_short(monkeypatch):
    """Keycloak slow → don't block API forever. Timeout must be ≤ 5s."""
    captured = {}

    def fake_get(url, *a, **kw):
        captured["timeout"] = kw.get("timeout")
        return _resp({"keys": []})

    monkeypatch.setattr(kv.httpx, "get", fake_get)
    kv._fetch_jwks()
    assert captured["timeout"] is not None
    assert captured["timeout"] <= 5.0
