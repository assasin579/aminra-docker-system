#!/usr/bin/env python3
"""Fail CI when domain FK boundary code reads Keycloak JWT `sub` directly.

`user['sub']` is ambiguous after SSO: in Keycloak-token paths it is the
Keycloak subject, while AMINRA domain FKs point at `users.id`. Boundary code
that reads/writes domain rows must use `auth.identity.resolve_canonical_*`.

This guard intentionally allows non-FK use in dedicated places such as
`auth/identity.py` (the resolver itself), `auth/rate_limit.py`, comments,
strings, and tests.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHED = [
    "auth/certificate_router.py",
    "auth/audit_router.py",
    "auth/submission_router.py",
    "auth/document_router.py",
    "auth/router.py",
    "auth/permissions.py",
    "supply_chain/batch_router.py",
    "supply_chain/supplier_router.py",
    "services/data_export.py",
]
NAMES = {"user", "owner", "current_user"}


def offenders(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in NAMES:
            sl = node.slice
            if isinstance(sl, ast.Constant) and sl.value == "sub":
                out.append(f"{path.relative_to(ROOT)}:{node.lineno}: direct {node.value.id}['sub']")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id in NAMES
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "sub"
            ):
                out.append(f"{path.relative_to(ROOT)}:{node.lineno}: direct {node.func.value.id}.get('sub')")
    return out


def main() -> int:
    found: list[str] = []
    for rel in WATCHED:
        found.extend(offenders(ROOT / rel))
    if found:
        print("Keycloak sub FK guard failed. Use resolve_canonical_user_id/tenant_id instead:", file=sys.stderr)
        for item in found:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print("Keycloak sub FK guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
