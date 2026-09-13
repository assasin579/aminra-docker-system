#!/usr/bin/env python3
"""Static tenant-boundary risk scanner for AMINRA.

This is a conservative scanner. Findings are review prompts, not definitive
vulnerabilities. It is designed to catch new routes/resource lookups that need
explicit tenant/IDOR review.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROUTE_ID_RE = re.compile(r"\{[^}]*?(id|uuid|filename|file_id|tenant_id|submission_id|certificate_id|business_id)[^}]*?\}")
RAW_ID_SQL_RE = re.compile(r"where\s+[^\n;]*(\bid\b|_id)\s*=", re.I)
TENANT_HINT_RE = re.compile(r"tenant_id|current_tenant|schema|business_id|owner_id|provider_id", re.I)
FILE_HINT_RE = re.compile(r"FileResponse|StreamingResponse|send_file|open\(|Path\(|CERT_PDF_DIR|DOCX|PDF", re.I)
AUTH_HINT_RE = re.compile(
    r"get_current_user|require_admin|require_provider|require_business|require_active_user|"
    r"_get_user_from_header_or_query|_enriched_user_from_header_or_query|decode_token|Authorization",
    re.I,
)
INTENDED_PUBLIC_HINT_RE = re.compile(
    r"Public endpoint|Public:|no auth|public_trace_enabled|invite_token|Liveness probe|available_templates|chat_stream",
    re.I,
)
SAFE_PUBLIC_PATH_RE = re.compile(
    r"^/(health|templates/available|chat/stream|render-pdf/health|api/supply-chain/batches/trace/|supplier-portal/)",
    re.I,
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _const(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _is_route_decorator(dec: ast.AST) -> tuple[str, str] | None:
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return None
    if dec.func.attr.lower() not in HTTP_METHODS or not dec.args:
        return None
    path = _const(dec.args[0])
    if path is None:
        return None
    return dec.func.attr.upper(), path


def scan_file(path: Path, repo: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [{"severity": "WARN", "kind": "syntax", "file": str(path.relative_to(repo)), "line": str(exc.lineno or 0), "message": str(exc)}]
    findings: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            src = ast.get_source_segment(text, node) or ""
            for dec in node.decorator_list:
                route = _is_route_decorator(dec)
                if not route:
                    continue
                method, route_path = route
                rel = str(path.relative_to(repo))
                line = str(getattr(node, "lineno", 0))
                has_auth = bool(AUTH_HINT_RE.search(src)) or "/admin" in route_path
                intended_public = bool(INTENDED_PUBLIC_HINT_RE.search(src)) or bool(SAFE_PUBLIC_PATH_RE.search(route_path))
                has_resource_id = bool(ROUTE_ID_RE.search(route_path))
                file_route = bool(FILE_HINT_RE.search(src))
                if intended_public:
                    if has_resource_id or file_route:
                        findings.append({"severity": "INFO", "kind": "intentional_public_reviewed", "file": rel, "line": line, "method": method, "path": route_path, "message": "public/token endpoint explicitly reviewed by scanner policy"})
                    continue
                if has_resource_id and not has_auth:
                    findings.append({"severity": "HIGH", "kind": "route_resource_without_auth_hint", "file": rel, "line": line, "method": method, "path": route_path, "message": "resource-id route has no auth dependency hint"})
                if file_route and not has_auth:
                    findings.append({"severity": "HIGH", "kind": "file_response_without_auth_hint", "file": rel, "line": line, "method": method, "path": route_path, "message": "file/stream route has no auth dependency hint"})
                if has_resource_id and has_auth and not TENANT_HINT_RE.search(src) and "/admin" not in route_path:
                    findings.append({"severity": "MEDIUM", "kind": "resource_route_without_tenant_hint", "file": rel, "line": line, "method": method, "path": route_path, "message": "resource-id route has auth but no nearby tenant/owner hint"})
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if RAW_ID_SQL_RE.search(node.value) and not TENANT_HINT_RE.search(node.value):
                findings.append({"severity": "MEDIUM", "kind": "raw_sql_id_lookup_without_tenant_hint", "file": str(path.relative_to(repo)), "line": str(getattr(node, "lineno", 0)), "message": node.value.strip().replace("\n", " ")[:240]})
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    backend = repo / "backend"
    files = [backend / "app.py"] + sorted((backend / "auth").glob("*_router.py")) + sorted((backend / "supply_chain").glob("*_router.py"))
    findings: list[dict[str, str]] = []
    for f in files:
        if f.exists():
            findings.extend(scan_file(f, repo))
    data = {"finding_count": len(findings), "findings": findings}
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = repo / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {len(findings)} findings to {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
