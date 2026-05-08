"""Schema-aware data wrapper for Jinja templates.

Eliminates the recurring `.get()` bug class observed in session 2026-05-06
(5+ bugs of shape `data.foo` or `s.role` blowing up under StrictUndefined
because the field happened to be Optional and absent from this payload).

Wrapping the data dict in a `SchemaAwareData` makes attribute/item access:

  * **Required field** → return value (validation already ensured presence).
  * **Optional field** → return value or `None` (no `.get()` needed).
  * **Unknown field**  → raise (catches typos like `data.foooo`).

Templates can now write `{{ data.tax_code or "—" }}` for any optional
field without `.get('tax_code')`, while retaining the typo-detection
property of `StrictUndefined`.

The wrapper is opt-in per-render: the renderer wraps `data` only if the
doc_type has a registered Pydantic schema. Unimplemented doc_types fall
back to the plain dict (current behaviour).
"""
from __future__ import annotations

from typing import Any, Iterator

from pydantic import BaseModel
from pydantic.fields import FieldInfo


__all__ = ["SchemaAwareData"]


class SchemaAwareData:
    """Read-only dict-like wrapper that consults a Pydantic schema on access.

    Designed for use as the `data` context in Jinja2 templates. Behaves like
    both a dict (`data['foo']`, `'foo' in data`, iteration) and an attribute
    bag (`data.foo`).
    """

    __slots__ = ("_data", "_fields", "_schema_name")

    def __init__(self, data: dict[str, Any], schema_cls: type[BaseModel]):
        # Pydantic v2 exposes field metadata via `model_fields: dict[str, FieldInfo]`.
        # We read it once at construction and stash a reference; never mutate.
        self._data: dict[str, Any] = data
        self._fields: dict[str, FieldInfo] = schema_cls.model_fields
        self._schema_name: str = schema_cls.__name__

    # ── Attribute access (template `{{ data.foo }}`) ───────────────────────

    def __getattr__(self, name: str) -> Any:
        # `__getattr__` is only called when normal lookup fails. The instance
        # __slots__ entries are reachable through default `__getattribute__`,
        # so we never have to special-case them here. Still, guard underscores
        # to avoid accidental recursion via dunder probes.
        if name.startswith("_"):
            raise AttributeError(name)

        if name not in self._fields and name not in self._data:
            # Neither in schema nor in payload — typo. Raise to catch it
            # (same intent as StrictUndefined). AttributeError is what Jinja
            # surfaces via UndefinedError.
            raise AttributeError(
                f"unknown field {name!r} on schema {self._schema_name}"
            )

        # Field is in the schema OR was added by a filter → safe to read;
        # missing optional → None.
        return self._data.get(name)

    # ── Item access (template `{{ data['foo'] }}` or `{% if 'x' in data %}`) ─

    def __getitem__(self, key: str) -> Any:
        if key not in self._fields and key not in self._data:
            raise KeyError(
                f"unknown field {key!r} on schema {self._schema_name}"
            )
        return self._data.get(key)

    def __contains__(self, key: object) -> bool:
        # Templates often write `{% if 'optional_thing' in data %}` to gate
        # rendering. Match dict semantics: True only if the key was actually
        # set in the payload (not just declared in the schema).
        return key in self._data

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    # ── Backward-compatible `.get()` ───────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Existing templates already call `.get('foo')` extensively. Keep
        the same semantics: return value if present, else default. Unknown-
        field protection still applies — typos raise, not silently default.
        """
        if key not in self._fields and key not in self._data:
            raise AttributeError(
                f"unknown field {key!r} on schema {self._schema_name}"
            )
        v = self._data.get(key)
        return v if v is not None else default

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def __repr__(self) -> str:
        return f"SchemaAwareData({self._schema_name}, {len(self._data)} fields set)"
