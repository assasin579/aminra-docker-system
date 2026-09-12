#!/usr/bin/env python3
"""AMINRA admin template file repair guard.

Purpose
-------
The backend serves only canonical DOCX files from:

    admin_templates/files/<doc_type>/<doc_type>_<vi|en>.docx

Old admin/manual upload paths can leave nested duplicates such as:

    admin_templates/files/<doc_type>/vi/<doc_type>_vi.docx

and earlier QA found tiny placeholder DOCX files advertised as valid templates.
This script is an idempotent guard: it scans a template-files directory,
classifies unsafe duplicate/placeholder DOCX files, optionally quarantines them,
and fails when unsafe files remain unless --apply fixed them.

It never deletes files. It moves quarantined files under:

    <templates-root>/.quarantine/<timestamp>/...

Usage examples
--------------
Dry-run against host-mounted/container path:
    python3 scripts/qa/repair-template-files.py --root /app/admin_templates/files

Apply repair:
    python3 scripts/qa/repair-template-files.py --root /app/admin_templates/files --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

MIN_REAL_DOCX_BYTES = 4096
LANGS = {"vi", "en"}


@dataclass(frozen=True)
class Finding:
    path: str
    reason: str
    size: int
    action: str


def is_valid_docx(path: Path) -> bool:
    """Return True when the file is a parseable Word DOCX package."""
    if not path.is_file() or path.suffix.lower() != ".docx":
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            return "word/document.xml" in names and "[Content_Types].xml" in names
    except zipfile.BadZipFile:
        return False


def canonical_parts(root: Path, path: Path) -> tuple[str | None, str | None, bool]:
    """Return (doc_type, lang, is_canonical) for a DOCX under root.

    Canonical layout is exactly <doc_type>/<doc_type>_<lang>.docx.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None, None, False
    parts = rel.parts
    if len(parts) != 2:
        return None, None, False
    doc_type = parts[0]
    stem = Path(parts[1]).stem
    for lang in LANGS:
        if stem == f"{doc_type}_{lang}":
            return doc_type, lang, True
    return doc_type, None, False


def corresponding_canonical(root: Path, path: Path) -> Path | None:
    """Find the canonical target for nested legacy duplicates, if inferable."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 3 and parts[1] in LANGS:
        doc_type = parts[0]
        lang = parts[1]
        if path.name == f"{doc_type}_{lang}.docx":
            return root / doc_type / path.name
    return None


def scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not root.exists():
        return findings

    for path in sorted(root.rglob("*.docx")):
        if ".quarantine" in path.parts:
            continue
        size = path.stat().st_size
        doc_type, lang, is_canonical = canonical_parts(root, path)
        valid = is_valid_docx(path)

        if is_canonical:
            if size < MIN_REAL_DOCX_BYTES or not valid:
                findings.append(
                    Finding(
                        path=str(path),
                        reason="canonical_docx_too_small_or_invalid",
                        size=size,
                        action="quarantine",
                    )
                )
            continue

        target = corresponding_canonical(root, path)
        if target and target.exists():
            findings.append(
                Finding(
                    path=str(path),
                    reason=f"legacy_nested_duplicate_of_{target.relative_to(root)}",
                    size=size,
                    action="quarantine",
                )
            )
            continue

        if size < MIN_REAL_DOCX_BYTES or not valid:
            findings.append(
                Finding(
                    path=str(path),
                    reason="noncanonical_docx_too_small_or_invalid",
                    size=size,
                    action="quarantine",
                )
            )

    return findings


def apply_quarantine(root: Path, findings: list[Finding]) -> list[dict[str, str]]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    quarantine_root = root / ".quarantine" / stamp
    moves: list[dict[str, str]] = []
    for finding in findings:
        src = Path(finding.path)
        rel = src.relative_to(root)
        dst = quarantine_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moves.append({"from": str(src), "to": str(dst), "reason": finding.reason})
    return moves


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="admin_templates/files", help="Template files root to scan")
    parser.add_argument("--apply", action="store_true", help="Move unsafe files to .quarantine")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    findings = scan(root)
    moves: list[dict[str, str]] = []
    if args.apply and findings:
        moves = apply_quarantine(root, findings)
        remaining = scan(root)
    else:
        remaining = findings

    payload = {
        "root": str(root),
        "apply": args.apply,
        "finding_count": len(findings),
        "remaining_count": len(remaining),
        "findings": [asdict(f) for f in findings],
        "moves": moves,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"root={payload['root']}")
        print(f"apply={payload['apply']} finding_count={payload['finding_count']} remaining_count={payload['remaining_count']}")
        for item in payload["findings"]:
            print(f"{item['action']} {item['reason']} size={item['size']} path={item['path']}")
        for item in moves:
            print(f"moved {item['from']} -> {item['to']} ({item['reason']})")

    return 0 if not remaining else 1


if __name__ == "__main__":
    raise SystemExit(main())
