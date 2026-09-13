#!/usr/bin/env python3
"""Build AMINRA route/auth/tenant inventory for IDOR release gates.

The output is intentionally conservative: ambiguous routes become high-risk
`deferred` rows instead of disappearing from the report.
"""
from __future__ import annotations

import argparse
import ast
import csv
import re
from dataclasses import dataclass
from pathlib import Path

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
PUBLIC_PATH_RE = re.compile(r"/(health|docs|openapi|api/submissions/certificates/public|api/supply-chain/batches/trace)")
EXPLICIT_PUBLIC_OR_LEGACY_RE = re.compile(
    r"/(auth/(business|provider)/register|auth/invite/|api/supply-chain/supplier-portal/|"
    r"stats$|topics$|placeholders$|templates/available|api/notifications/push-public-key|chat/stream$|chat$)"
)
FILE_WORDS = ("file", "pdf", "docx", "photo", "attachment", "export", "template", "company-profile")
RESOURCE_PARAM_RE = re.compile(r"\{[^}]*?(id|uuid|code|filename|trace_id|business_id|submission_id|certificate_id)[^}]*?\}")

# Existing evidence files/suites. This map is deliberately family-level; the
# confidence report still distinguishes representative coverage from 1:1 route
# coverage.
COVERAGE_RULES = [
    (re.compile(r"/api/supply-chain/(suppliers|supplier-portal|materials|processes|batches|certificate-risk-alerts)"), "tests/test_supply_chain_batches.py; tests/test_supply_chain_supplier_eligibility_routes.py; tests/test_unauth_route_boundaries.py"),
    (re.compile(r"/api/submissions|/dossiers|/api/audits"), "tests/test_unauth_route_boundaries.py; tests/uat/test_uat_c_tenant_isolation.py"),
    (re.compile(r"/api/users/me|/api/users/me/export-data|/api/users/me/request-deletion"), "tests/test_dual_auth_cross_tenant_unit.py; tests/test_unauth_route_boundaries.py"),
    (re.compile(r"/api/notifications"), "tests/test_unauth_route_boundaries.py; notification tenant-scope DB checks"),
    (re.compile(r"/auth/admin|/admin/"), "tests/test_unauth_route_boundaries.py; tests/test_keycloak_admin_edge.py"),
    (re.compile(r"/auth/business|/auth/provider|/auth/company|/auth/invite"), "tests/uat/test_uat_c_tenant_isolation.py; tests/test_unauth_route_boundaries.py"),
    (re.compile(r"/generate-document|/api/documents|/api/templates|/templates/.*/download"), "tests/test_generate_document_export_security.py; tests/test_certificate_pdf_integrity_smoke.py; tests/uat/test_uat_c_tenant_isolation.py"),
    (re.compile(r"/api/supply-chain/batches/trace|/api/submissions/certificates/public"), "tests/test_public_trace_*; tests/test_certificate_pdf_integrity_smoke.py"),
    (re.compile(r"/industry-schemas|/standard-types"), "tests/test_unauth_route_boundaries.py; schema/standard tenant route coverage"),
    (re.compile(r"/jobs/|/reviews/|/ingest|/evaluate|/rewrite|/chat"), "tests/test_unauth_route_boundaries.py; tests/uat/test_uat_c_tenant_isolation.py; public chat rate-limit smoke"),
    (re.compile(r"/auth/notification-preferences"), "tests/test_unauth_route_boundaries.py; notification preferences authenticated-user smoke"),
]

@dataclass
class Route:
    method: str
    path: str
    handler: str
    source_file: str
    lineno: int
    router_name: str
    function_source: str


def _const(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _join(prefix: str, path: str) -> str:
    if not prefix:
        return path or "/"
    return (prefix.rstrip("/") + "/" + path.lstrip("/")).rstrip("/") or "/"


def _import_router_aliases(app_py: Path) -> dict[str, tuple[str, str]]:
    tree = ast.parse(app_py.read_text(encoding="utf-8"))
    aliases: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                aliases[local] = (node.module, alias.name)
    return aliases


def _include_prefixes(app_py: Path) -> dict[str, str]:
    tree = ast.parse(app_py.read_text(encoding="utf-8"))
    prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "include_router":
            continue
        if not node.args or not isinstance(node.args[0], ast.Name):
            continue
        name = node.args[0].id
        prefix = ""
        for kw in node.keywords:
            if kw.arg == "prefix":
                prefix = _const(kw.value) or ""
        prefixes[name] = prefix
    return prefixes


def _module_to_path(backend: Path, module: str) -> Path:
    return backend / (module.replace(".", "/") + ".py")


def _route_prefixes(backend: Path) -> dict[tuple[Path, str], str]:
    app_py = backend / "app.py"
    aliases = _import_router_aliases(app_py)
    include_prefixes = _include_prefixes(app_py)
    result: dict[tuple[Path, str], str] = {(app_py, "app"): ""}
    for local_name, prefix in include_prefixes.items():
        mod_and_export = aliases.get(local_name)
        if not mod_and_export:
            continue
        module, exported = mod_and_export
        result[(_module_to_path(backend, module), exported)] = prefix
    return result


def _decorator_route(dec: ast.AST) -> tuple[str, str, str] | None:
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return None
    method = dec.func.attr.lower()
    if method not in HTTP_METHODS:
        return None
    value = dec.func.value
    if not isinstance(value, ast.Name):
        return None
    if not dec.args:
        return None
    path = _const(dec.args[0])
    if path is None:
        return None
    return value.id, method.upper(), path


def _routes_from_file(path: Path, prefixes: dict[tuple[Path, str], str], backend: Path) -> list[Route]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    out: list[Route] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            route = _decorator_route(dec)
            if not route:
                continue
            router_name, method, raw_path = route
            prefix = prefixes.get((path, router_name), "" if router_name == "app" else None)
            if prefix is None:
                continue
            try:
                source = ast.get_source_segment(text, node) or ""
            except Exception:
                source = ""
            out.append(Route(
                method=method,
                path=_join(prefix, raw_path),
                handler=node.name,
                source_file=str(path.relative_to(backend.parent)),
                lineno=getattr(node, "lineno", 0),
                router_name=router_name,
                function_source=source,
            ))
    return out


def auth_signal(route: Route) -> str:
    s = route.function_source
    p = route.path
    if PUBLIC_PATH_RE.search(p):
        return "public-intended"
    if EXPLICIT_PUBLIC_OR_LEGACY_RE.search(p):
        return "public-explicit-or-legacy"
    if "require_admin" in s or "/admin" in p:
        return "require_admin"
    if "require_provider" in s:
        return "require_provider"
    if "require_business" in s:
        return "require_business"
    if "get_current_user" in s or "require_active_user" in s or "_enriched_user_from_header_or_query" in s or "_get_user_from_header_or_query" in s:
        return "get_current_user"
    return "no-auth-explicit-review"


def tenant_class(route: Route, auth: str) -> str:
    p = route.path
    s = route.function_source
    if auth in {"public-intended", "public-explicit-or-legacy"}:
        if "trace" in p or "public" in p:
            return "public_sealed_snapshot"
        if "invite" in p or "supplier-portal" in p:
            return "public_token_scoped"
        return "public_safe_or_legacy"
    if auth == "require_admin" or "/admin" in p:
        return "admin_global"
    if "/api/supply-chain" in p:
        return "tenant_scoped_supply_chain"
    if any(x in p for x in ["business", "dossier", "audit", "submission", "certificate"]):
        return "provider_business_scoped" if "business_id" in p or "require_provider" in s else "tenant_scoped"
    if any(x in p for x in ["users/me", "notifications", "documents", "templates", "company", "industry-schemas", "standard-types", "generate-document", "evaluate", "rewrite", "ingest"]):
        return "tenant_scoped"
    if auth in {"get_current_user", "require_business", "require_provider"}:
        return "tenant_scoped"
    if auth == "no-auth-explicit-review":
        return "explicit_review_required"
    return "unknown"


def risk_class(route: Route, auth: str, tenant: str) -> str:
    p = route.path.lower()
    if auth in {"public-intended", "public-explicit-or-legacy"}:
        return "P1_PUBLIC_SEALED" if ("trace" in p or "public" in p) else ("P0_RESOURCE_IDOR" if RESOURCE_PARAM_RE.search(route.path) or route.method != "GET" else "P2_HEALTH_OR_STATIC")
    if auth in {"public/unknown", "no-auth-explicit-review"}:
        return "P0_RESOURCE_IDOR" if RESOURCE_PARAM_RE.search(route.path) or route.method != "GET" else "P1_TENANT_LIST"
    if any(w in p for w in FILE_WORDS):
        return "P0_FILE_OBJECT"
    if "/admin" in p:
        return "P0_ADMIN_GLOBAL"
    if RESOURCE_PARAM_RE.search(route.path) or route.method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "P0_RESOURCE_IDOR"
    if tenant.startswith("tenant") or tenant == "provider_business_scoped":
        return "P1_TENANT_LIST"
    return "P2_HEALTH_OR_STATIC"


def coverage(path: str, risk: str, auth: str) -> tuple[str, str, str, str]:
    for pattern, tests in COVERAGE_RULES:
        if pattern.search(path):
            return "covered", tests, "", ""
    if risk.startswith("P0_"):
        return "deferred", "", "qa-owner", "inventory-generated: add explicit negative test before production signoff"
    if risk.startswith("P1_"):
        return "deferred", "", "qa-owner", "representative coverage only; add route-family test for 8/10+"
    return "covered" if auth != "public/unknown" else "deferred", "low-risk/static smoke", "", ""


def build(repo: Path) -> list[dict[str, str]]:
    backend = repo / "backend"
    prefixes = _route_prefixes(backend)
    files = {p for p, _router in prefixes.keys()}
    # Include adjacent routers even if not mounted due parser drift; they will be ignored if no prefix known.
    for glob in ["auth/*_router.py", "supply_chain/*_router.py"]:
        files.update(backend.glob(glob))
    routes: list[Route] = []
    for file in sorted(files):
        routes.extend(_routes_from_file(file, prefixes, backend))
    rows = []
    for r in sorted(routes, key=lambda x: (x.path, x.method, x.source_file, x.lineno)):
        auth = auth_signal(r)
        tenant = tenant_class(r, auth)
        risk = risk_class(r, auth, tenant)
        status, tests, owner, reason = coverage(r.path, risk, auth)
        rows.append({
            "method": r.method,
            "path": r.path,
            "handler": r.handler,
            "source_file": f"{r.source_file}:{r.lineno}",
            "auth_signal": auth,
            "tenant_class": tenant,
            "risk_class": risk,
            "coverage_test": tests,
            "coverage_status": status,
            "owner": owner,
            "defer_reason": reason,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    rows = build(repo)
    out = Path(args.out)
    if not out.is_absolute():
        out = repo / out
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "method", "path", "handler", "source_file", "auth_signal", "tenant_class",
        "risk_class", "coverage_test", "coverage_status", "owner", "defer_reason",
    ]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} routes to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
