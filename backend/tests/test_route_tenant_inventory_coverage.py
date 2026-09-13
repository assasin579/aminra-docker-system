"""Tenant/IDOR route inventory coverage gate.

This is a release-readiness guard, not a product feature test. It fails when
high-risk backend routes have no explicit tenant/auth classification and no
mapped negative-coverage evidence.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path


def _repo_root() -> Path:
    """Find repo root both on host (`repo/backend/tests`) and in container (`/app/tests`)."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "docs").exists() and ((parent / "backend").exists() or (parent / "pytest.ini").exists()):
            return parent
        if parent.name == "backend" and (parent.parent / "docs").exists():
            return parent.parent
    # Container fallback after `docker cp`: /app is backend root, docs may be copied under /app/docs.
    for parent in [here.parent, *here.parents]:
        if (parent / "pytest.ini").exists():
            return parent
    return here.parents[2]


REPO_ROOT = _repo_root()
DEFAULT_INVENTORY = REPO_ROOT / "docs/qa/2026-09-13-tenant-idor-confidence-8of10/route-inventory.tsv"


def _inventory_path() -> Path:
    return Path(os.environ.get("ROUTE_TENANT_INVENTORY", DEFAULT_INVENTORY))


def _rows() -> list[dict[str, str]]:
    path = _inventory_path()
    assert path.exists(), (
        f"Missing tenant route inventory: {path}. Run "
        "`python3 scripts/qa/build_route_tenant_inventory.py --repo . --out "
        "docs/qa/2026-09-13-tenant-idor-confidence-8of10/route-inventory.tsv`"
    )
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def test_route_inventory_has_required_columns():
    rows = _rows()
    assert rows, "route inventory is empty"
    required = {
        "method",
        "path",
        "handler",
        "source_file",
        "auth_signal",
        "tenant_class",
        "risk_class",
        "coverage_test",
        "coverage_status",
        "owner",
        "defer_reason",
    }
    assert required.issubset(rows[0].keys())


def test_p0_routes_have_explicit_coverage_or_owned_deferral():
    offenders = []
    for row in _rows():
        if not row["risk_class"].startswith("P0_"):
            continue
        covered = row["coverage_status"] == "covered" and row["coverage_test"]
        owned_deferral = (
            row["coverage_status"] == "deferred"
            and row["owner"]
            and row["defer_reason"]
        )
        if not (covered or owned_deferral):
            offenders.append(
                f"{row['method']} {row['path']} risk={row['risk_class']} "
                f"tenant={row['tenant_class']} auth={row['auth_signal']}"
            )
    assert not offenders, "P0 routes lacking coverage/owned deferral:\n" + "\n".join(offenders[:80])


def test_no_unknown_auth_or_tenant_class_for_p0_p1_routes():
    offenders = []
    for row in _rows():
        if not row["risk_class"].startswith(("P0_", "P1_")):
            continue
        if row["auth_signal"] in {"public/unknown", "unknown"} or row["tenant_class"] == "unknown":
            offenders.append(
                f"{row['method']} {row['path']} risk={row['risk_class']} "
                f"tenant={row['tenant_class']} auth={row['auth_signal']}"
            )
    assert not offenders, "P0/P1 routes with unknown auth/tenant classification:\n" + "\n".join(offenders[:80])
