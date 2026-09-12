#!/usr/bin/env python3
"""Seed an idempotent public-enabled sealed traceability QA fixture.

This intentionally uses docker compose + psql so it works against the local
sandbox without requiring app secrets or direct DB credentials on the host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

FIXTURE_BATCH_CODE = "QA-TRACE-PUBLISHED-SEALED-001"
TRACE_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"aminra:qa:public-trace:{FIXTURE_BATCH_CODE}"))


def canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def sql_quote(value: str) -> str:
    return value.replace("'", "''")


def build_fixture() -> tuple[str, str]:
    # Keep the sealed snapshot deterministic so integrity hashes are stable
    # across repeated QA smoke runs. Database audit timestamps may still use NOW().
    now = datetime(2026, 9, 11, tzinfo=timezone.utc).isoformat()
    sealed = {
        "snapshot_version": 2,
        "hash_algorithm": "sha256",
        "batch_code": FIXTURE_BATCH_CODE,
        "product_name": "QA Published Sealed Halal Trace Fixture",
        "started_at": now,
        "completed_at": now,
        "approved_by": "qa-seed@aminra.local",
        "approved_at": now,
        "compliance_score": 98,
        "company_name": "AMINRA QA Business",
        "batch": {
            "id": "qa-fixture-logical-id",
            "batch_code": FIXTURE_BATCH_CODE,
            "product_name": "QA Published Sealed Halal Trace Fixture",
            "status": "completed",
            "started_at": now,
            "completed_at": now,
            "created_at": now,
            "compliance_score": 98,
        },
        "company": {"name": "AMINRA QA Business"},
        "process": {
            "id": None,
            "name": "QA Public Trace Seal Process",
            "description": "Deterministic fixture proving public trace positive 200 path.",
            "version": "qa-1",
        },
        "steps": [
            {
                "step_name": "QA receive material",
                "performed_by": "QA Operator",
                "started_at": now,
                "completed_at": now,
                "status": "completed",
                "approved_by": "qa-seed@aminra.local",
                "approved_at": now,
                "notes": "Seeded fixture step; not production lot data.",
                "checklist": [{"label": "Fixture sealed", "checked": True}],
                "has_photo": False,
            }
        ],
        "materials": [
            {
                "material_name": "QA Halal Input",
                "name": "QA Halal Input",
                "sku": "QA-MAT-TRACE-001",
                "category": "qa",
                "halal_risk": "safe",
                "supplier_name": "QA Supplier",
                "eligibility_snapshot": {"status": "active", "source_of_truth": "cb"},
                "quantity": "1",
                "unit": "lot",
            }
        ],
        "certificates": [
            {
                "supplier_name": "QA Supplier",
                "cert_type": "Halal",
                "cert_number": "QA-CERT-TRACE-001",
                "issuing_body": "QA Certification Body",
                "issued_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            }
        ],
    }
    sealed_json = canonical_json(sealed)
    integrity_hash = hashlib.sha256(sealed_json.encode("utf-8")).hexdigest()
    return sealed_json, integrity_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()

    sealed_json, integrity_hash = build_fixture()
    sql = f"""
\\set ON_ERROR_STOP on
WITH target_tenant AS (
    SELECT tenant_id
      FROM users
     WHERE role = 'business'
       AND status = 'active'
       AND tenant_id IS NOT NULL
     ORDER BY (email = 'demo-biz@aminra.vn') DESC, created_at ASC
     LIMIT 1
), upserted AS (
    INSERT INTO production_batches (
        tenant_id, batch_code, product_name, status,
        started_at, completed_at, compliance_score, notes,
        integrity_hash, sealed_data, approved_by, approved_at,
        public_trace_id, public_trace_enabled
    )
    SELECT tenant_id,
           '{FIXTURE_BATCH_CODE}',
           'QA Published Sealed Halal Trace Fixture',
           'completed'::batch_status,
           NOW(), NOW(), 98,
           'Idempotent QA fixture for public trace positive smoke; not production lot data.',
           '{integrity_hash}',
           '{sql_quote(sealed_json)}'::jsonb,
           'qa-seed@aminra.local',
           NOW(),
           '{TRACE_UUID}'::uuid,
           true
      FROM target_tenant
    ON CONFLICT (tenant_id, batch_code)
    DO UPDATE SET
        product_name = EXCLUDED.product_name,
        status = EXCLUDED.status,
        completed_at = EXCLUDED.completed_at,
        compliance_score = EXCLUDED.compliance_score,
        notes = EXCLUDED.notes,
        integrity_hash = EXCLUDED.integrity_hash,
        sealed_data = EXCLUDED.sealed_data,
        approved_by = EXCLUDED.approved_by,
        approved_at = EXCLUDED.approved_at,
        public_trace_id = EXCLUDED.public_trace_id,
        public_trace_enabled = true,
        updated_at = NOW()
    RETURNING batch_code, public_trace_id, public_trace_enabled, integrity_hash
)
SELECT batch_code, public_trace_id, public_trace_enabled, integrity_hash FROM upserted;
"""
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres-db",
        "psql",
        "-U",
        "aminra_user",
        "-d",
        "aminra",
    ]
    result = subprocess.run(cmd, cwd=args.repo_root, input=sql, text=True)
    if result.returncode != 0:
        return result.returncode
    print(f"TRACE_ID={TRACE_UUID}")
    print(f"BATCH_CODE={FIXTURE_BATCH_CODE}")
    print(f"INTEGRITY_HASH={integrity_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
