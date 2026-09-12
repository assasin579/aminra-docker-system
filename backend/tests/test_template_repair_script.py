"""Regression tests for scripts/qa/repair-template-files.py."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path


def script_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "scripts" / "qa" / "repair-template-files.py",  # /app/tests in container
        here.parents[2] / "scripts" / "qa" / "repair-template-files.py",  # repo/backend/tests on host
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise AssertionError(f"repair-template-files.py not found in candidates: {candidates}")


def load_module():
    spec = importlib.util.spec_from_file_location("repair_template_files", script_path())
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_docx(path: Path, body: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", f"<w:document>{body}</w:document>")
        zf.writestr("word/styles.xml", "x" * 5000)


def test_quarantines_legacy_nested_duplicate_when_canonical_exists(tmp_path: Path) -> None:
    repair = load_module()
    root = tmp_path / "admin_templates" / "files"
    canonical = root / "halal_policy" / "halal_policy_vi.docx"
    nested = root / "halal_policy" / "vi" / "halal_policy_vi.docx"
    write_docx(canonical, "canonical")
    write_docx(nested, "legacy duplicate")

    findings = repair.scan(root)

    assert len(findings) == 1
    assert Path(findings[0].path) == nested
    assert findings[0].reason == "legacy_nested_duplicate_of_halal_policy/halal_policy_vi.docx"

    moves = repair.apply_quarantine(root, findings)

    assert not nested.exists()
    assert canonical.exists()
    assert moves and Path(moves[0]["to"]).exists()
    assert repair.scan(root) == []


def test_quarantines_tiny_or_invalid_canonical_placeholder(tmp_path: Path) -> None:
    repair = load_module()
    root = tmp_path / "admin_templates" / "files"
    bad = root / "has_manual" / "has_manual_vi.docx"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"not a docx placeholder")

    findings = repair.scan(root)

    assert len(findings) == 1
    assert Path(findings[0].path) == bad
    assert findings[0].reason == "canonical_docx_too_small_or_invalid"


def test_valid_canonical_docx_is_left_alone(tmp_path: Path) -> None:
    repair = load_module()
    root = tmp_path / "admin_templates" / "files"
    canonical = root / "halal_policy" / "halal_policy_en.docx"
    write_docx(canonical, "canonical")

    assert repair.scan(root) == []
