from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_FK_BOUNDARY_FILES = [
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


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def _raw_user_sub_refs(rel: str) -> list[str]:
    tree = ast.parse(_read(rel), filename=rel)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in {"user", "owner"}:
            sl = node.slice
            if isinstance(sl, ast.Constant) and sl.value == "sub":
                offenders.append(f"{rel}:{node.lineno} {node.value.id}['sub']")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"user", "owner"}
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "sub"
            ):
                offenders.append(f"{rel}:{node.lineno} {node.func.value.id}.get('sub')")
    return offenders


def test_domain_fk_boundaries_do_not_read_token_sub_directly():
    offenders: list[str] = []
    for rel in DOMAIN_FK_BOUNDARY_FILES:
        offenders.extend(_raw_user_sub_refs(rel))
    assert offenders == []


def test_canonical_identity_helpers_are_used_for_domain_fk_boundaries():
    expected = {
        "auth/certificate_router.py": "resolve_canonical_tenant_id",
        "auth/audit_router.py": "resolve_canonical_tenant_id",
        "auth/submission_router.py": "resolve_canonical_tenant_id",
        "auth/document_router.py": "resolve_canonical_user_id",
        "auth/router.py": "resolve_canonical_user_id",
        "auth/permissions.py": "resolve_canonical_user_id",
        "supply_chain/batch_router.py": "resolve_canonical_user_id",
        "supply_chain/supplier_router.py": "resolve_canonical_tenant_id",
        "services/data_export.py": "resolve_canonical_user_id",
    }
    missing = [f"{rel}: {needle}" for rel, needle in expected.items() if needle not in _read(rel)]
    assert missing == []
