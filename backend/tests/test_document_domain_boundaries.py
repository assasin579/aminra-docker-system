from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from auth import document_router

DOC = '11111111-1111-4111-8111-111111111111'
TENANT = UUID('22222222-2222-4222-8222-222222222222')


@pytest.mark.asyncio
async def test_read_only_member_cannot_select_a_current_document(monkeypatch):
    async def deny(_user, permission):
        assert permission == 'can_edit'
        raise HTTPException(403, 'No editing capability')

    monkeypatch.setattr(document_router, 'check_permission_db', deny)
    monkeypatch.setattr(document_router, 'resolve_canonical_tenant_id', AsyncMock(return_value=TENANT))
    db = AsyncMock()
    db.fetchrow.return_value = {'id': DOC, 'doc_type': 'halal_policy'}
    member = {'role': 'business', 'is_owner': False, 'permissions': {'can_edit': False}}
    with pytest.raises(HTTPException) as caught:
        await document_router.promote_document(DOC, user=member, db=db)
    assert caught.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.fixture
def evaluation_app(monkeypatch, tmp_path):
    # app import creates operational folders; isolate them from the read-only source.
    monkeypatch.chdir(tmp_path)
    import app
    return app


@pytest.mark.asyncio
async def test_ai_upload_denies_read_only_member_before_file_or_llm(evaluation_app, monkeypatch):
    app = evaluation_app
    gate = AsyncMock(side_effect=HTTPException(403, 'Upload forbidden'))
    validate = AsyncMock()
    from unittest.mock import Mock
    llm = Mock()
    monkeypatch.setattr(app, 'check_permission_db', gate)
    monkeypatch.setattr(app, 'validate_upload', validate)
    monkeypatch.setattr(app, 'evaluate_document', llm)
    with pytest.raises(HTTPException) as caught:
        await app.evaluate_doc(request=None, file=None, user={'role':'business'},
            doc_type=None, previous_context=None, lang='vi')
    assert caught.value.status_code == 403
    gate.assert_awaited_once_with({'role':'business'}, 'can_upload')
    validate.assert_not_awaited()
    llm.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('save_fails', [False, True])
async def test_ai_response_distinguishes_saved_from_failed_persistence(evaluation_app, monkeypatch, save_fails):
    from io import BytesIO
    from unittest.mock import Mock, MagicMock
    from fastapi import UploadFile
    from services import document_ingestion
    from auth import db as auth_db
    app = evaluation_app
    monkeypatch.setattr(app, 'check_permission_db', AsyncMock())
    monkeypatch.setattr(app, 'validate_upload', AsyncMock(return_value=b'synthetic text'))
    monkeypatch.setattr(app, 'evaluate_document', Mock(return_value={'compliance_score':80,'doc_type':'general'}))
    pool=MagicMock();conn=AsyncMock();pool.acquire.return_value.__aenter__=AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__=AsyncMock(return_value=False)
    monkeypatch.setattr(auth_db, 'get_pool', lambda: pool)
    monkeypatch.setattr(app, 'resolve_canonical_user_id', AsyncMock(return_value=TENANT))
    monkeypatch.setattr(app, 'resolve_canonical_tenant_id', AsyncMock(return_value=TENANT))
    save=AsyncMock(side_effect=RuntimeError('synthetic unavailable') if save_fails else None,
                   return_value={'id':DOC})
    monkeypatch.setattr(document_ingestion, 'save_library_document', save)
    result=await app.evaluate_doc(request=None,file=UploadFile(BytesIO(b'text'),filename='test.txt'),
        user={'role':'business'},doc_type=None,previous_context=None,lang='vi')
    assert result.compliance_score==80
    assert result.document_save_status == ('failed' if save_fails else 'saved')
    assert result.document_id == (None if save_fails else DOC)
    assert bool(result.document_save_error) == save_fails


@pytest.mark.asyncio
async def test_existing_ai_evaluation_denies_read_only_before_mutation(monkeypatch):
    gate=AsyncMock(side_effect=HTTPException(403,'Upload forbidden'))
    monkeypatch.setattr(document_router,'check_permission_db',gate)
    db=AsyncMock()
    with pytest.raises(HTTPException) as caught:
        await document_router.evaluate_existing_document(DOC,lang='vi',user={'role':'business'},db=db)
    assert caught.value.status_code==403
    db.fetchrow.assert_not_awaited()
    db.execute.assert_not_awaited()
