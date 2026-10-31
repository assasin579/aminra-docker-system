"""Controlled migration of the verified 054/manual-052-053 installation.

Default rehearses DDL in a rolled-back transaction; --apply commits.
DATABASE_URL must be the migration credential. Never uses an application role.
"""
import argparse
import asyncio
import importlib.util
import os
from pathlib import Path
import asyncpg

ROOT = Path(__file__).resolve().parents[2]

async def run(apply):
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s'")
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext('aminra-j1j2-schema'))")
        heads = set(await conn.fetchval('SELECT array_agg(version_num) FROM alembic_version'))
        if heads != {'054_requirements_versions'}:
            raise RuntimeError(f'Unexpected lineage: {sorted(heads)}')
        # These objects were manually deployed. Stamp only after verifying their
        # required columns, indexes, FK and enforced acceptance-state constraints.
        cols = {r['column_name'] for r in await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='mobile_offline_replay_operations'")}
        required = {'id','tenant_id','user_id','visit_id','operation_type','route_key','resource_key','idempotency_key','request_hash','response_status','response_body','conflict_reason','created_at','updated_at'}
        if not required <= cols:
            raise RuntimeError('052 schema mismatch')
        indexes = {r['indexname']:r['indexdef'] for r in await conn.fetch("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public'")}
        for name in ['uq_mobile_offline_replay_scope_key','idx_mobile_offline_replay_visit_created','idx_mobile_offline_replay_user_created','idx_audit_visits_provider_report_accepted']:
            if name not in indexes:
                raise RuntimeError(f'Missing index: {name}')
        expected_indexes = {
            'uq_mobile_offline_replay_scope_key': ['UNIQUE INDEX', '(tenant_id, operation_type, route_key, resource_key, idempotency_key)'],
            'idx_mobile_offline_replay_visit_created': ['(tenant_id, visit_id, created_at DESC)'],
            'idx_mobile_offline_replay_user_created': ['(tenant_id, user_id, created_at DESC)'],
            'idx_audit_visits_provider_report_accepted': ['(provider_id, report_accepted_at DESC)', "report_accepted"],
        }
        for name, tokens in expected_indexes.items():
            if not all(token in indexes[name] for token in tokens):
                raise RuntimeError(f'Index definition mismatch: {name}')
        constraints = {r['conname']:r['definition'] for r in await conn.fetch("SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid='audit_visits'::regclass AND convalidated")}
        for name in ['audit_visits_report_accepted_by_fkey','audit_visits_status_check','ck_audit_visits_report_acceptance_consistency']:
            if name not in constraints:
                raise RuntimeError(f'Missing validated constraint: {name}')
        for token in ['report_accepted_at IS NOT NULL','report_accepted_by IS NOT NULL','report_accepted_at IS NULL','report_accepted_by IS NULL']:
            if token not in constraints['ck_audit_visits_report_acceptance_consistency']:
                raise RuntimeError('053 consistency constraint mismatch')
        spec=importlib.util.spec_from_file_location('attachment_migration', ROOT/'backend/alembic/versions/055_dossier_document_attachments.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        statements=[]
        class Operations:
            @staticmethod
            def execute(sql): statements.append(sql)
        module.op=Operations
        module.upgrade()
        for sql in statements: await conn.execute(sql)
        await conn.execute("UPDATE alembic_version SET version_num='056_j1j2_lineage_merge' WHERE version_num='054_requirements_versions'")
        if apply: await tx.commit()
        else: await tx.rollback()
        print('APPLIED 056_j1j2_lineage_merge' if apply else 'REHEARSAL PASS; all DDL rolled back')
    except BaseException:
        await tx.rollback();raise
    finally: await conn.close()

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true')
    asyncio.run(run(parser.parse_args().apply))
