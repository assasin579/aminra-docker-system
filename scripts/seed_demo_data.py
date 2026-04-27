#!/usr/bin/env python3
"""Seed demo data for AMINRA MVP demos.

Idempotent: cleans up old `*@demo.aminra.vn` users + their data first
(only when `--reset` flag is passed), then inserts a fresh, predictable
seed:

    1× admin (admin@aminra.com — uses Vault password if set)
    1× provider owner   — cb-demo@demo.aminra.vn / DemoP@ss2026
    2× business owners  — biz-demo-{1,2}@demo.aminra.vn / DemoP@ss2026
    1× auditor          — auditor-demo@demo.aminra.vn / DemoP@ss2026

    3× submissions in different states (reviewing / revision_required / approved)
    2× certificates (1 active, 1 with expiry in 30 days for alert demo)
    1× audit visit scheduled for tomorrow

Run:
    python scripts/seed_demo_data.py            # add (skip existing)
    python scripts/seed_demo_data.py --reset    # delete demo users first, then add

Run inside backend container so DATABASE_URL + Vault env are loaded:
    docker exec aminra-docker-system-aminra-backend-1 \\
        sh -c '. /vault/secrets/env.sh; python /app/seed_demo_data.py --reset'
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4


DEMO_PASSWORD = "DemoP@ss2026"
DEMO_DOMAIN = "@demo.aminra.vn"

DEMO_USERS = [
    {
        "email":        f"cb-demo{DEMO_DOMAIN}",
        "role":         "provider",
        "is_owner":     True,
        "company_name": "Halal Certification Vietnam (Demo)",
        "company_code": "CB-DEMO-001",
    },
    {
        "email":        f"biz-demo-1{DEMO_DOMAIN}",
        "role":         "business",
        "is_owner":     True,
        "company_name": "Demo Foods Co.",
        "company_code": "BIZ-DEMO-001",
    },
    {
        "email":        f"biz-demo-2{DEMO_DOMAIN}",
        "role":         "business",
        "is_owner":     True,
        "company_name": "Demo Beverages Ltd.",
        "company_code": "BIZ-DEMO-002",
    },
    {
        "email":        f"auditor-demo{DEMO_DOMAIN}",
        "role":         "provider",
        "is_owner":     False,                    # sub-user under CB
        "company_name": "Halal Certification Vietnam (Demo)",
        "company_code": "AUDITOR-DEMO-001",
    },
]


async def _connect():
    import asyncpg
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set. Source vault env first.", file=sys.stderr)
        sys.exit(2)
    return await asyncpg.connect(url)


def _hash_password(pw: str) -> str:
    """Match the bcrypt hash format used by the rest of the app."""
    sys.path.insert(0, "/app")
    from auth.password import hash_password
    return hash_password(pw)


async def reset_demo_data(conn):
    """Wipe everything previously seeded under @demo.aminra.vn so re-seed
    is fully idempotent."""
    print("[seed] Wiping existing @demo.aminra.vn data…")

    # Cascade-aware deletes — order matters because of FK
    user_ids = [r["id"] for r in await conn.fetch(
        "SELECT id FROM users WHERE email LIKE $1", f"%{DEMO_DOMAIN}"
    )]
    if not user_ids:
        print("[seed]   nothing to wipe")
        return

    tenant_ids = [r["tenant_id"] for r in await conn.fetch(
        "SELECT DISTINCT tenant_id FROM users WHERE id = ANY($1::uuid[])", user_ids,
    ) if r["tenant_id"]]

    # Anchor proofs first (FK on cert/batch)
    await conn.execute(
        "DELETE FROM cert_anchor_proofs WHERE cert_id IN ("
        " SELECT id FROM halal_certificates WHERE business_tenant = ANY($1::uuid[]))",
        tenant_ids or [uuid4()],
    )
    # Audit visits + items + NCRs
    await conn.execute(
        "DELETE FROM audit_visits WHERE business_tenant = ANY($1::uuid[]) OR provider_id = ANY($2::uuid[])",
        tenant_ids or [uuid4()], user_ids,
    )
    # Submission revision requests
    await conn.execute(
        "DELETE FROM submission_revision_requests WHERE submission_id IN ("
        " SELECT id FROM submissions WHERE business_tenant = ANY($1::uuid[]) OR provider_id = ANY($2::uuid[]))",
        tenant_ids or [uuid4()], user_ids,
    )
    # Submission comments
    await conn.execute(
        "DELETE FROM submission_comments WHERE submission_id IN ("
        " SELECT id FROM submissions WHERE business_tenant = ANY($1::uuid[]) OR provider_id = ANY($2::uuid[]))",
        tenant_ids or [uuid4()], user_ids,
    )
    # Halal certs
    await conn.execute(
        "DELETE FROM halal_certificates WHERE business_tenant = ANY($1::uuid[]) OR issued_by = ANY($2::uuid[])",
        tenant_ids or [uuid4()], user_ids,
    )
    # Submissions
    await conn.execute(
        "DELETE FROM submissions WHERE business_tenant = ANY($1::uuid[]) OR provider_id = ANY($2::uuid[])",
        tenant_ids or [uuid4()], user_ids,
    )
    # Documents + tokens + notifications
    await conn.execute("DELETE FROM documents WHERE tenant_id = ANY($1::uuid[]) OR user_id = ANY($2::uuid[])",
                       tenant_ids or [uuid4()], user_ids)
    await conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ANY($1::uuid[])", user_ids)
    await conn.execute("DELETE FROM deletion_tokens WHERE user_id = ANY($1::uuid[])", user_ids)
    await conn.execute("DELETE FROM notifications WHERE user_id = ANY($1::uuid[])", user_ids)
    # Self-assessments
    await conn.execute("DELETE FROM self_assessments WHERE tenant_id = ANY($1::uuid[])", tenant_ids or [uuid4()])
    # Suppliers / materials / batches
    await conn.execute("DELETE FROM materials WHERE tenant_id = ANY($1::uuid[])", tenant_ids or [uuid4()])
    await conn.execute("DELETE FROM suppliers WHERE tenant_id = ANY($1::uuid[])", tenant_ids or [uuid4()])
    await conn.execute("DELETE FROM production_batches WHERE tenant_id = ANY($1::uuid[])", tenant_ids or [uuid4()])
    # Audit logs (denormalized — SET NULL on delete; safe to keep)
    # Finally users
    await conn.execute("DELETE FROM users WHERE id = ANY($1::uuid[])", user_ids)
    print(f"[seed]   wiped {len(user_ids)} user(s) + their data")


async def seed_users(conn) -> dict:
    """Insert demo users. Returns map email→id."""
    pw_hash = _hash_password(DEMO_PASSWORD)
    out = {}
    for u in DEMO_USERS:
        existing = await conn.fetchval("SELECT id FROM users WHERE email = $1", u["email"])
        if existing:
            out[u["email"]] = existing
            print(f"[seed] user {u['email']:40} EXISTS → {existing}")
            continue
        new_id = uuid4()
        # Determine tenant_id: owner == self, sub-user == owner's id
        tenant_id = new_id if u["is_owner"] else None
        await conn.execute(
            """
            INSERT INTO users (id, email, password_hash, role, status, is_owner,
                               company_name, company_code, tenant_id)
            VALUES ($1, $2, $3, $4::user_role, 'active', $5,
                    $6, $7, $8)
            """,
            new_id, u["email"], pw_hash, u["role"], u["is_owner"],
            u["company_name"], u["company_code"], tenant_id,
        )
        out[u["email"]] = new_id
        print(f"[seed] user {u['email']:40} CREATED → {new_id}")

    # Auditor: tenant_id should point to CB owner
    cb_id = out[f"cb-demo{DEMO_DOMAIN}"]
    auditor_email = f"auditor-demo{DEMO_DOMAIN}"
    await conn.execute(
        "UPDATE users SET tenant_id = $1 WHERE email = $2",
        cb_id, auditor_email,
    )
    return out


async def seed_documents(conn, biz_user_id, biz_tenant_id) -> list:
    """Seed 3 documents owned by biz."""
    out = []
    for i, name in enumerate(
        ["application_form.pdf", "ingredient_list.pdf", "sop_cleaning.pdf"], 1,
    ):
        doc_id = uuid4()
        await conn.execute(
            """
            INSERT INTO documents (id, filename, original_filename, user_id, tenant_id,
                                   doc_type, status, file_size)
            VALUES ($1, $2, $3, $4, $5, $6, 'uploaded', 102400)
            """,
            doc_id, f"demo-{i:02d}-{name}", name,
            biz_user_id, biz_tenant_id,
            ["application", "ingredient_list", "sop"][i - 1],
        )
        out.append(doc_id)
    return out


async def seed_submissions(conn, users: dict) -> dict:
    """Create 3 submissions in different states for demo richness."""
    cb_id = users[f"cb-demo{DEMO_DOMAIN}"]
    biz1_id = users[f"biz-demo-1{DEMO_DOMAIN}"]
    biz2_id = users[f"biz-demo-2{DEMO_DOMAIN}"]

    # Get/create docs for biz1
    docs1 = await seed_documents(conn, biz1_id, biz1_id)
    docs2 = await seed_documents(conn, biz2_id, biz2_id)

    out = {}

    # 1) Reviewing submission
    sub1 = uuid4()
    await conn.execute(
        """
        INSERT INTO submissions (id, business_tenant, provider_id, document_ids, status,
                                 notes, company_name, submitted_at, deadline)
        VALUES ($1, $2, $3, $4::uuid[], 'reviewing',
                'Demo - Hồ sơ chứng nhận sản phẩm bánh mì gối', 'Demo Foods Co.',
                NOW() - INTERVAL '5 days', NOW() + INTERVAL '15 days')
        """,
        sub1, biz1_id, cb_id, docs1,
    )
    out["reviewing"] = sub1

    # 2) Revision-required submission with feedback
    sub2 = uuid4()
    await conn.execute(
        """
        INSERT INTO submissions (id, business_tenant, provider_id, document_ids, status,
                                 notes, company_name, submitted_at, deadline,
                                 revision_round, revision_requested_at)
        VALUES ($1, $2, $3, $4::uuid[], 'revision_required',
                'Demo - Sản phẩm nước trái cây', 'Demo Beverages Ltd.',
                NOW() - INTERVAL '10 days', NOW() + INTERVAL '5 days',
                1, NOW() - INTERVAL '2 days')
        """,
        sub2, biz2_id, cb_id, docs2,
    )
    # Add a revision request entry
    await conn.execute(
        """
        INSERT INTO submission_revision_requests
            (submission_id, round, requester_id, requester_name, feedback, document_feedback)
        VALUES ($1, 1, $2, 'Halal Certification Vietnam (Demo)',
                'Cần bổ sung chứng nhận Halal của nguyên liệu hương liệu + sửa quy trình rửa thiết bị theo MS 1500 mục 5.4',
                $3::jsonb)
        """,
        sub2, cb_id,
        json.dumps([
            {"document_id": str(docs2[0]), "issue": "Thiếu seal JAKIM", "severity": "major", "suggestion": "Tải lại bản có seal"},
            {"document_id": str(docs2[2]), "issue": "Quy trình rửa thiết bị giữa ca", "severity": "critical", "suggestion": "Bổ sung istinjak step"},
        ]),
    )
    out["revision_required"] = sub2

    # 3) Approved submission (will get cert below)
    sub3 = uuid4()
    await conn.execute(
        """
        INSERT INTO submissions (id, business_tenant, provider_id, document_ids, status,
                                 notes, company_name, submitted_at, updated_at)
        VALUES ($1, $2, $3, $4::uuid[], 'approved',
                'Demo - Đã được duyệt, chuẩn bị cấp cert', 'Demo Foods Co.',
                NOW() - INTERVAL '20 days', NOW() - INTERVAL '2 days')
        """,
        sub3, biz1_id, cb_id, docs1,
    )
    out["approved"] = sub3
    return out


async def seed_certs(conn, users: dict):
    """1 active cert for biz1 + 1 expiring-soon cert for biz2 (alert demo)."""
    cb_id = users[f"cb-demo{DEMO_DOMAIN}"]
    biz1 = users[f"biz-demo-1{DEMO_DOMAIN}"]
    biz2 = users[f"biz-demo-2{DEMO_DOMAIN}"]

    # 1. Active cert (12 months valid) — used by Flow 1 (verify) + Flow 5 (PDF)
    cert1 = uuid4()
    await conn.execute(
        """
        INSERT INTO halal_certificates (id, cert_number, issued_by, business_tenant,
                                        company_name, issue_date, expiry_date, status)
        VALUES ($1, 'HALAL-2026-DEMO', $2, $3,
                'Demo Foods Co.', $4, $5, 'active')
        """,
        cert1, cb_id, biz1, date.today() - timedelta(days=30), date.today() + timedelta(days=335),
    )

    # 2. Expiring-soon cert (25 days left) — Flow 16 lifecycle alert demo
    cert2 = uuid4()
    await conn.execute(
        """
        INSERT INTO halal_certificates (id, cert_number, issued_by, business_tenant,
                                        company_name, issue_date, expiry_date, status)
        VALUES ($1, 'HALAL-2025-EXPIRING', $2, $3,
                'Demo Beverages Ltd.', $4, $5, 'active')
        """,
        cert2, cb_id, biz2, date.today() - timedelta(days=340), date.today() + timedelta(days=25),
    )
    print("[seed] certs HALAL-2026-DEMO + HALAL-2025-EXPIRING created")


async def seed_audit_visit(conn, users: dict, submissions: dict):
    """Schedule 1 audit visit for tomorrow."""
    cb_id = users[f"cb-demo{DEMO_DOMAIN}"]
    auditor_id = users[f"auditor-demo{DEMO_DOMAIN}"]
    biz1 = users[f"biz-demo-1{DEMO_DOMAIN}"]

    # Need a checklist template — create one if missing
    tpl_id = await conn.fetchval(
        "SELECT id FROM audit_checklist_templates WHERE name = $1",
        "Demo MS 1500 checklist",
    )
    if not tpl_id:
        tpl_id = uuid4()
        await conn.execute(
            """
            INSERT INTO audit_checklist_templates (id, provider_id, name, standard, items)
            VALUES ($1, $2, 'Demo MS 1500 checklist', 'MS 1500:2019', $3::jsonb)
            """,
            tpl_id, cb_id,
            json.dumps([
                {"category": "Cleaning", "criteria": "Equipment cleaned between batches", "severity": "critical"},
                {"category": "Storage", "criteria": "Halal + non-halal segregation", "severity": "critical"},
                {"category": "Documentation", "criteria": "SOP available on-site", "severity": "major"},
            ]),
        )

    visit_id = uuid4()
    await conn.execute(
        """
        INSERT INTO audit_visits (id, business_tenant, provider_id, auditor_id,
                                  template_id, visit_type, status, scheduled_date,
                                  location)
        VALUES ($1, $2, $3, $4, $5, 'initial', 'scheduled', $6, 'Bình Dương, VN')
        """,
        visit_id, biz1, cb_id, auditor_id, tpl_id,
        date.today() + timedelta(days=1),
    )
    print(f"[seed] audit visit scheduled for {date.today() + timedelta(days=1)}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Wipe existing @demo.aminra.vn data before seeding")
    args = parser.parse_args()

    conn = await _connect()
    try:
        if args.reset:
            await reset_demo_data(conn)
        users = await seed_users(conn)
        submissions = await seed_submissions(conn, users)
        await seed_certs(conn, users)
        await seed_audit_visit(conn, users, submissions)

        print()
        print("=" * 70)
        print("  DEMO DATA READY")
        print("=" * 70)
        print(f"  Password (all):  {DEMO_PASSWORD}")
        print(f"  Provider login:  cb-demo{DEMO_DOMAIN}")
        print(f"  Business 1:      biz-demo-1{DEMO_DOMAIN}")
        print(f"  Business 2:      biz-demo-2{DEMO_DOMAIN}")
        print(f"  Auditor:         auditor-demo{DEMO_DOMAIN}")
        print(f"  Demo cert:       HALAL-2026-DEMO  (active)")
        print(f"  Expiring cert:   HALAL-2025-EXPIRING  (25 days left)")
        print()
        print(f"  Verify URL:      http://localhost:3100/verify/HALAL-2026-DEMO")
        print()
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
