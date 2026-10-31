"""Domain boundary acceptance against a disposable, schema-only PostgreSQL copy."""
from io import BytesIO
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from tests.test_submission_j1_j2_disposable import db, case  # noqa: F401
from auth import document_router, submission_router
from services.document_library import select_current_version
from services.document_ingestion import save_library_document


@pytest.mark.asyncio
async def test_current_selection_preserves_chronology_and_is_idempotent(db, case, monkeypatch):
    tenant = case['ids']['business_a']
    doc = case['docs']['permit-v2']['id']
    root = case['docs']['permit-v1']['id']
    before = dict(await db.fetchrow('SELECT uploaded_at, approval_status, version_parent_id, version_number FROM documents WHERE id=$1', doc))
    result = await select_current_version(db, tenant_id=tenant, document_id=doc, actor_id=tenant)
    assert result['root_document_id'] == str(root) and result['changed']
    monkeypatch.setattr(document_router, 'is_feature_enabled', AsyncMock(return_value=False))
    detail = await document_router.get_document(str(doc), user=case['users']['business_a'], db=db)
    assert detail.is_current_selection is True
    selected_at = await db.fetchval('SELECT selected_at FROM document_current_versions WHERE current_document_id=$1', doc)
    replay = await select_current_version(db, tenant_id=tenant, document_id=doc, actor_id=tenant)
    assert not replay['changed']
    assert await db.fetchval('SELECT selected_at FROM document_current_versions WHERE current_document_id=$1', doc) == selected_at
    assert dict(await db.fetchrow('SELECT uploaded_at, approval_status, version_parent_id, version_number FROM documents WHERE id=$1', doc)) == before
    assert await db.fetchval("SELECT count(*) FROM audit_logs WHERE entity_id=$1 AND action='document.current_version_selected'", doc) == 1
    # Same type is insufficient to share a version family.
    with pytest.raises(Exception) as caught:
        async with db.transaction():
            await db.execute('INSERT INTO document_current_versions VALUES ($1,$2,$3,$1,now())', tenant, case['docs']['manual-v1']['id'], root)
    assert caught.value.sqlstate == '23514'


@pytest.mark.asyncio
async def test_current_selection_cross_tenant_rejected(db, case):
    with pytest.raises(HTTPException) as caught:
        await select_current_version(db, tenant_id=case['ids']['business_b'],
            document_id=case['initial_docs'][0], actor_id=case['ids']['business_b'])
    assert caught.value.status_code == 404
    assert await db.fetchval('SELECT count(*) FROM document_current_versions WHERE tenant_id=$1', case['ids']['business_b']) == 0


@pytest.mark.asyncio
async def test_library_all_view_preserves_same_type_files(db, case, monkeypatch):
    monkeypatch.setattr(document_router, 'is_feature_enabled', AsyncMock(return_value=False))
    result = await document_router.list_documents(page=1, page_size=100, doc_type='permit', status=None,
        view='all', user=case['users']['business_a'], db=db)
    assert {d.id for d in result.documents} == {str(case['docs'][key]['id']) for key in ('permit-v1','permit-v2')}
    legacy = await document_router.list_documents(page=1, page_size=100, doc_type='permit', status=None,
        view='latest_by_type', user=case['users']['business_a'], db=db)
    assert legacy.total == 1


@pytest.mark.asyncio
async def test_cb_history_excludes_unsubmitted_same_tenant_document(db, case):
    result = await submission_router.submission_doc_revisions(str(case['ids']['submission']), 'permit', user=case['users']['cb_p'], db=db)
    assert {r['id'] for r in result['revisions']} == {str(case['docs']['permit-v1']['id'])}
    # A legitimate historical packet remains accessible after the current packet changes.
    from services.submission_revisions import request_revision
    await request_revision(db, submission_id=case['ids']['submission'], requester_id=str(case['users']['cb_p']['id']), requester_name='Synthetic CB',
        feedback='Synthetic revision', document_feedback=[])
    await db.execute('UPDATE submissions SET document_ids=$1 WHERE id=$2', [case['docs']['permit-v2']['id']], case['ids']['submission'])
    historical = await submission_router.submission_doc_revisions(str(case['ids']['submission']), 'permit', user=case['users']['cb_p'], db=db)
    assert {r['id'] for r in historical['revisions']} == {str(case['docs'][key]['id']) for key in ('permit-v1','permit-v2')}


@pytest.mark.asyncio
async def test_legacy_upload_creates_canonical_attachment_and_replays(db, case, monkeypatch, tmp_path):
    monkeypatch.setattr(document_router, 'UPLOAD_DIR', tmp_path)
    key=uuid4()
    async def upload():
        file=UploadFile(BytesIO(b'%PDF-1.4\nsynthetic document\n%%EOF'),filename='policy.pdf',headers=Headers({'content-type':'application/pdf'}))
        return await document_router.upload_document(file=file,doc_type='policy',dossier_id=case['ids']['dossier'],
            idempotency_key=key,user=case['users']['business_a'],db=db)
    result=await upload();replay=await upload()
    assert result['id']==replay['id'] and result['attachment_state']=='attached'
    assert await db.fetchval('SELECT count(*) FROM dossier_document_attachments WHERE document_id=$1 AND dossier_id=$2', result['id'], case['ids']['dossier']) == 1
    assert len(list(tmp_path.rglob('*.pdf')))==1


@pytest.mark.asyncio
async def test_library_persistence_failure_cleans_physical_file(db, case, monkeypatch, tmp_path):
    monkeypatch.setattr(document_router, 'UPLOAD_DIR', tmp_path)
    with pytest.raises(Exception):
        await save_library_document(db, tenant_id=case['ids']['business_a'], actor_id=uuid4(),
            filename='failure.pdf',content=b'%PDF-1.4\nsynthetic\n%%EOF',mime_type='application/pdf')
    assert list(tmp_path.rglob('*.pdf'))==[]


@pytest.mark.asyncio
async def test_supersede_reconciles_current_selection_without_changing_upload_date(db, case, monkeypatch):
    from tests.test_submission_j1_j2_disposable import synthetic_request
    monkeypatch.setattr(document_router, '_require_versioning_flag', AsyncMock())
    monkeypatch.setattr(document_router, '_audit_strict', AsyncMock())
    tenant=case['ids']['business_a']
    old=case['docs']['policy-v1']['id']
    new=uuid4()
    await db.execute("UPDATE documents SET approval_status='approved' WHERE id=$1", old)
    await db.execute("""INSERT INTO documents (id,filename,original_filename,file_path,file_size,mime_type,user_id,tenant_id,doc_type,approval_status)
        VALUES ($1,'new.pdf','new.pdf','synthetic://new',10,'application/pdf',$2,$2,'policy','approved')""", new,tenant)
    before=await db.fetchval('SELECT uploaded_at FROM documents WHERE id=$1',new)
    await select_current_version(db,tenant_id=tenant,document_id=new,actor_id=tenant)
    await select_current_version(db,tenant_id=tenant,document_id=old,actor_id=tenant)
    await document_router.supersede_document(str(old),document_router._SupersedeRequest(new_document_id=str(new)),
        request=synthetic_request(),user=case['users']['business_a'],db=db)
    pointer=await db.fetchrow('SELECT root_document_id,current_document_id FROM document_current_versions WHERE tenant_id=$1',tenant)
    assert pointer['root_document_id']==old and pointer['current_document_id']==new
    assert await db.fetchval('SELECT count(*) FROM document_current_versions WHERE tenant_id=$1',tenant)==1
    assert await db.fetchval('SELECT uploaded_at FROM documents WHERE id=$1',new)==before
    assert await db.fetchval('SELECT approval_status FROM documents WHERE id=$1',old)=='obsolete'


@pytest.mark.asyncio
async def test_two_dossiers_same_document_type_stay_visible_in_library(db, case, monkeypatch, tmp_path):
    from services.document_ingestion import attach_dossier_document
    monkeypatch.setattr(document_router,'UPLOAD_DIR',tmp_path)
    monkeypatch.setattr(document_router,'is_feature_enabled',AsyncMock(return_value=False))
    other=uuid4();tenant=case['ids']['business_a']
    await db.execute("""INSERT INTO dossiers (id,tenant_id,standard_type_id,title,status,created_by,requirements_version_id,requirements_binding_status)
        VALUES ($1,$2,$3,'Other synthetic dossier','draft',$2,$4,'bound')""",other,tenant,case['ids']['standard'],case['ids']['requirements'])
    uploaded=[]
    for dossier in (case['ids']['dossier'],other):
        result=await attach_dossier_document(db,dossier_id=dossier,tenant_id=tenant,actor_id=tenant,
            doc_type='policy',idempotency_key=uuid4(),file=UploadFile(BytesIO(b'%PDF-1.4\nsynthetic\n%%EOF'),filename='policy.pdf',headers=Headers({'content-type':'application/pdf'})))
        uploaded.append(result['document_id'])
    library=await document_router.list_documents(page=1,page_size=100,doc_type='policy',status=None,view='all',user=case['users']['business_a'],db=db)
    assert set(uploaded) <= {d.id for d in library.documents}
    for dossier,document in zip((case['ids']['dossier'],other),uploaded):
        assert await db.fetchval('SELECT count(*) FROM dossier_document_attachments WHERE dossier_id=$1 AND document_id=$2',dossier,document)==1


@pytest.mark.asyncio
async def test_ai_library_save_has_stable_identity_and_separate_score_provenance(db, case, monkeypatch, tmp_path):
    import json
    monkeypatch.setattr(document_router, 'UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(document_router, 'is_feature_enabled', AsyncMock(return_value=False))
    tenant=case['ids']['business_a'];content=b'%PDF-1.4\nsynthetic saved AI evidence\n%%EOF'
    saved=await save_library_document(db,tenant_id=tenant,actor_id=tenant,filename='ai.pdf',content=content,
        mime_type='application/pdf',doc_type='policy',evaluation_result={'compliance_score':84,'overall_status':'compliant'})
    row=await db.fetchrow('SELECT file_path,file_size FROM documents WHERE id=$1',saved['id'])
    from pathlib import Path
    assert Path(row['file_path']).read_bytes()==content and row['file_size']==len(content)
    assert await db.fetchval('SELECT count(*) FROM dossier_document_attachments WHERE document_id=$1',saved['id'])==0
    # Legacy CB score projection must never be mislabelled as the original AI score.
    await db.execute('UPDATE documents SET compliance_score=91,evaluation_result=$1::jsonb WHERE id=$2',
        json.dumps({'compliance_score':84,'overall_status':'cb_approved','cb_score':91}),saved['id'])
    detail=await document_router.get_document(saved['id'],user=case['users']['business_a'],db=db)
    assert detail.ai_score==84 and detail.cb_score==91 and detail.compliance_score==91
