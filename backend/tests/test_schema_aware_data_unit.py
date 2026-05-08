"""Unit tests for services/schema_aware_data.SchemaAwareData.

Eliminates `.get()` recurring bug class observed in session 2026-05-06.
Three behaviour contracts:
  1. Optional field absent → access returns None (no exception).
  2. Required field present → access returns value (validation guaranteed it).
  3. Unknown field (not in schema, not in data) → access raises (typo guard).

Backward compat: existing `.get(key, default)` calls keep their semantics.
Filter-added fields (PlaceholderFiller, FormatFilter) that aren't in the
schema are still readable so we don't break the 3-stage pipeline.
"""
from __future__ import annotations

from typing import Optional

import pytest
from pydantic import BaseModel, Field

from services.schema_aware_data import SchemaAwareData


# ── Fixture schema (mimics CompanyProfileData shape) ───────────────────────


class _Demo(BaseModel):
    """Required: business_name. Optional: tax_code, address."""
    business_name: str = Field(..., min_length=1)
    tax_code: Optional[str] = Field(None)
    address: Optional[str] = Field(None)


# ── Optional field absent: no exception, returns None ─────────────────────


class TestOptionalAbsent:
    def test_attr_access_returns_none(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        assert d.tax_code is None
        assert d.address is None

    def test_item_access_returns_none(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        assert d["tax_code"] is None

    def test_get_with_default(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        assert d.get("tax_code", "—") == "—"

    def test_truthy_or_idiom_works(self):
        """Templates rely on `{{ data.tax_code or '—' }}`. Verify None is falsy."""
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        assert (d.tax_code or "—") == "—"


# ── Required + optional present: returns value ─────────────────────────────


class TestPresent:
    def test_required_attr(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        assert d.business_name == "ABC"

    def test_optional_attr_when_filled(self):
        d = SchemaAwareData(
            {"business_name": "ABC", "tax_code": "0123456789"}, _Demo
        )
        assert d.tax_code == "0123456789"

    def test_get_returns_value_not_default_when_present(self):
        d = SchemaAwareData(
            {"business_name": "ABC", "tax_code": "X"}, _Demo
        )
        assert d.get("tax_code", "—") == "X"


# ── Unknown field: raises (typo guard) ────────────────────────────────────


class TestTypoGuard:
    def test_typo_attr_raises(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        with pytest.raises(AttributeError, match="unknown field 'foooo'"):
            _ = d.foooo

    def test_typo_item_raises(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        with pytest.raises(KeyError, match="unknown field 'foooo'"):
            _ = d["foooo"]

    def test_typo_get_raises(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        with pytest.raises(AttributeError, match="unknown field 'foooo'"):
            d.get("foooo", "default")


# ── Filter-added fields (not in schema, present in data) ───────────────────


class TestFilterAddedField:
    """PlaceholderFiller/FormatFilter may inject derived fields. They should
    be readable even if not in the original Pydantic schema."""

    def test_underscore_prefixed_keys_blocked_by_attr(self):
        """Underscore-prefixed keys are rejected at __getattr__ to prevent
        accidental dunder probe recursion. Use item access if templates
        actually need to read `_derived` (uncommon)."""
        d = SchemaAwareData(
            {"business_name": "ABC", "_derived": "computed"}, _Demo
        )
        with pytest.raises(AttributeError):
            _ = d._derived

    def test_data_only_field_item_access(self):
        d = SchemaAwareData(
            {"business_name": "ABC", "watermark_label": "DRAFT"}, _Demo
        )
        # Item access bypasses the underscore guard.
        assert d["watermark_label"] == "DRAFT"

    def test_data_only_field_attr_no_underscore(self):
        d = SchemaAwareData(
            {"business_name": "ABC", "watermark_label": "DRAFT"}, _Demo
        )
        assert d.watermark_label == "DRAFT"


# ── dict-like interface (templates iterate with `for k, v in data.items()`) ─


class TestDictInterface:
    def test_contains_only_for_present_keys(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        assert "business_name" in d
        # Optional and unset → not in data, even though declared in schema.
        assert "tax_code" not in d

    def test_iter_yields_present_keys(self):
        d = SchemaAwareData(
            {"business_name": "ABC", "address": "123 Main"}, _Demo
        )
        assert sorted(d) == ["address", "business_name"]

    def test_len(self):
        d = SchemaAwareData({"business_name": "ABC"}, _Demo)
        assert len(d) == 1

    def test_items_keys_values(self):
        payload = {"business_name": "ABC", "address": "X"}
        d = SchemaAwareData(payload, _Demo)
        assert dict(d.items()) == payload
        assert sorted(d.keys()) == ["address", "business_name"]
        assert sorted(d.values()) == ["ABC", "X"]
