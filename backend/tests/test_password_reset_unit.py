"""Unit tests for password validation + reset router edge cases.

The router itself is exercised end-to-end in test_password_reset_integration.py.
This file covers the helpers and tight unit-level invariants.
"""
from __future__ import annotations

import pytest

from auth.password import (
    WeakPasswordError,
    hash_password,
    validate_password_strength,
    verify_password,
)


class TestValidatePasswordStrength:
    @pytest.mark.parametrize("good", [
        "Strong0Password",
        "AB12345abc",
        "MyP@ssw0rd!Long",
    ])
    def test_accepts_compliant(self, good):
        validate_password_strength(good)  # should not raise

    @pytest.mark.parametrize("bad,reason", [
        ("Short1A",            "10 ký tự"),
        ("alllowercase1abc",   "chữ hoa"),
        ("ALLUPPERCASE1ABC",   "chữ thường"),
        ("NoDigitsHereXYZyz",  "chữ số"),
    ])
    def test_rejects_weak(self, bad, reason):
        with pytest.raises(WeakPasswordError, match=reason):
            validate_password_strength(bad)


class TestHashAndVerify:
    def test_hash_then_verify_roundtrip(self):
        h = hash_password("Strong0Password")
        assert verify_password("Strong0Password", h) is True
        assert verify_password("Strong0Passwor", h) is False
        # Hash is non-deterministic (bcrypt salt)
        assert h != hash_password("Strong0Password")
