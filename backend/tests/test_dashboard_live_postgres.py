"""Real serving PostgreSQL; schema + all fixture writes roll back per test."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from fastapi import HTTPException
from services.requirements_versions import publish_requirements_version
from services.dossier_readiness import compute_dossier_readiness
from services.dossier_dashboard import build_dashboard
from auth.submission_router import cb_performance_90d


@pytest.fixture
async def data():
    db = await asyncpg.connect(os.environ['DATABASE_URL'])
    tx = db.transaction(isolation='repeatable_read'); await tx.start()
    try:
        # Run pending declarations on this connection only; never commit the rehearsal.
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        # asyncpg executes captured statements; no secondary DB/environment.
        from unittest.mock import patch
        import alembic.op
        pending = await db.fetchval("SELECT to_regclass('public.standard_requirement_versions')") is None
        for prefix in (['053','054'] if pending else []):
            file = next((Path(__file__).parents[1]/'alembic/versions').glob(prefix+'*'))
            spec = importlib.util.spec_from_file_location(prefix, file); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            sql=[]
            with patch.object(alembic.op,'execute',sql.append): module.upgrade()
            for statement in sql: await db.execute(statement)
        admin, business, other, auditor = [uuid4() for _ in range(4)]
        for uid, role, owner, tenant in [(admin,'provider',True,admin),(business,'business',True,business),(other,'business',True,other),(auditor,'provider',False,admin)]:
            await db.execute("INSERT INTO users(id,email,role,company_name,status,is_owner,tenant_id) VALUES($1,$2,$3,'QA dashboard','active',$4,$5)",uid,f'qa-dashboard-{uid}@example.com',role,owner,tenant)
        standard=await db.fetchval("INSERT INTO standard_types(code,name_vi) VALUES($1,'QA standard') RETURNING id",'qa_'+uuid4().hex[:16])
        actor={'sub':str(admin),'app_user_id':str(admin),'_keycloak':True,'realm_roles':['platform_admin'],'role':'provider','email':f'qa-dashboard-{admin}@example.com'}
        yield db,admin,business,other,auditor,standard,actor
    finally:
        await tx.rollback();await db.close()


async def publish(data, slots):
    db,admin,_,_,_,standard,actor=data
    for i,(code,required) in enumerate(slots):
        await db.execute('INSERT INTO standard_doc_types(standard_type_id,doc_type,required,display_order) VALUES($1,$2,$3,$4)',standard,code,required,i)
    return await publish_requirements_version(db,standard_type_id=standard,actor=actor,actor_id=admin)


async def test_publication_is_idempotent_and_legacy_never_backfilled(data):
    db,admin,business,_,_,standard,actor=data
    legacy=await db.fetchval("INSERT INTO dossiers(tenant_id,standard_type_id,title) VALUES($1,$2,'legacy') RETURNING id",business,standard)
    first=await publish(data,[('halal_policy',True),('has_manual',True)])
    second=await publish_requirements_version(db,standard_type_id=standard,actor=actor,actor_id=admin)
    assert first['requirements_version_id']==second['requirements_version_id'] and second['unchanged']
    readiness=await compute_dossier_readiness(db,dossier_id=str(legacy),tenant_id=str(business))
    assert readiness['state']=='requirements_unknown' and readiness['readiness_percent'] is None
    async with db.transaction():
        with pytest.raises(asyncpg.RaiseError):
            # Isolate expected trigger error inside its own savepoint below.
            async with db.transaction():
                await db.execute('UPDATE standard_requirement_version_slots SET required=false WHERE requirements_version_id=$1',first['requirements_version_id'])


async def test_profiles_are_tenant_scoped_and_optional_only_is_na(data):
    db,_,business,other,_,standard,_=data
    version=await publish(data,[('halal_policy',False)])
    a=await db.fetchval("INSERT INTO dossiers(tenant_id,standard_type_id,title,requirements_version_id,requirements_binding_status) VALUES($1,$2,'own',$3,'bound') RETURNING id",business,standard,version['requirements_version_id'])
    await db.execute("INSERT INTO dossiers(tenant_id,standard_type_id,title) VALUES($1,$2,'other')",other,standard)
    r=await build_dashboard(db,str(business))
    assert r['total_dossiers']==1 and r['profiles'][0]['dossiers'][0]['id']==str(a)
    d=r['profiles'][0]['dossiers'][0];assert d['requirements_version_number']==1
    assert d['readiness']['state']=='requirements_no_required_slots' and d['readiness']['readiness_percent'] is None
    with pytest.raises(HTTPException) as e:await compute_dossier_readiness(db,dossier_id=str(a),tenant_id=str(other))
    assert e.value.status_code==404


async def test_ai_compliant_is_not_review_approval_and_uses_exact_round_documents(data):
    db,admin,business,_,_,standard,_=data
    version=await publish(data,[('halal_policy',True),('has_manual',True)])
    dossier=await db.fetchval("INSERT INTO dossiers(tenant_id,standard_type_id,title,requirements_version_id,requirements_binding_status) VALUES($1,$2,'bound',$3,'bound') RETURNING id",business,standard,version['requirements_version_id'])
    docs=[]
    for kind,approval,score in [('halal_policy','approved',80),('has_manual','draft',100)]:
        docs.append(await db.fetchval("INSERT INTO documents(filename,original_filename,user_id,tenant_id,dossier_id,doc_type,approval_status,compliance_score,evaluation_result) VALUES('qa.txt','qa.txt',$1,$1,$2,$3,$4,$5,'{\"overall_status\":\"compliant\"}') RETURNING id",business,dossier,kind,approval,score))
    await db.execute("INSERT INTO submissions(business_tenant,provider_id,document_ids,requirements_version_id,requirements_binding_status) VALUES($1,$2,$3,$4,'bound')",business,admin,docs,version['requirements_version_id'])
    r=await compute_dossier_readiness(db,dossier_id=str(dossier),tenant_id=str(business))
    assert r['readiness_percent']==0  # Business approval + AI compliant is not CB review.
    sub=await db.fetchrow('SELECT * FROM submissions WHERE business_tenant=$1 AND requirements_version_id=$2',business,version['requirements_version_id'])
    await db.execute("UPDATE submissions SET status='reviewing' WHERE id=$1",sub['id'])
    await db.execute("INSERT INTO submission_evaluations(submission_id,auditor_id,score,notes) VALUES($1,$2,90,'QA human review')",sub['id'],admin)
    from auth.submission_router import approve_final
    await approve_final(str(sub['id']),user={'sub':str(admin),'app_user_id':str(admin),'email':f'qa-dashboard-{admin}@example.com','role':'provider','is_owner':True,'tenant_id':str(admin),'realm_roles':['cb_admin']},db=db)
    r=await compute_dossier_readiness(db,dossier_id=str(dossier),tenant_id=str(business))
    assert r['readiness_percent']==75 and r['state']=='ready_for_decision'
    assert [s['state'] for s in r['requirement_slots']]==['approved','approved']
    # A later approved upload outside submitted evidence cannot satisfy this round.
    await db.execute("INSERT INTO documents(filename,original_filename,user_id,tenant_id,dossier_id,doc_type,approval_status) VALUES('later.txt','later.txt',$1,$1,$2,'has_manual','approved')",business,dossier)
    again=await compute_dossier_readiness(db,dossier_id=str(dossier),tenant_id=str(business))
    assert again['readiness_percent']==75
    await db.execute('UPDATE submissions SET revision_round=1 WHERE id=$1',sub['id'])
    next_round=await compute_dossier_readiness(db,dossier_id=str(dossier),tenant_id=str(business))
    assert next_round['readiness_percent']==0  # Prior round approval cannot carry forward.


async def test_cb_performance_uses_only_own_accepted_reports_and_two_windows(data):
    db,admin,business,other,auditor,_,_=data
    # Another provider is needed to prove tenant filtering with valid FKs.
    await db.execute("UPDATE users SET role='provider' WHERE id=$1",other)
    for provider,status,days in [(admin,'report_accepted',5),(admin,'report_accepted',105),(other,'report_accepted',5),(admin,'report_submitted',5)]:
        await db.execute("INSERT INTO audit_visits(business_tenant,provider_id,auditor_id,visit_type,scheduled_date,status,report_accepted_at,report_accepted_by,created_at) VALUES($1,$2,$3,'initial',CURRENT_DATE-10,$4::varchar,CASE WHEN $4::varchar='report_accepted' THEN NOW()-($5::double precision*interval '1 day') ELSE NULL END,CASE WHEN $4::varchar='report_accepted' THEN $2::uuid ELSE NULL END,NOW()-interval '120 days')",business,provider,auditor,status,days)
    r=await cb_performance_90d({'role':'provider','app_user_id':str(admin),'realm_roles':['cb_admin']},db)
    assert r['window_days']==90 and r['attribution']=='report_accepted_at'
    assert r['total']['completed']=={'current_90d':1,'previous_90d':1}
    assert len(r['auditors'])==1
    with pytest.raises(HTTPException) as e:await cb_performance_90d({'role':'provider','app_user_id':str(auditor),'is_owner':True},db)
    assert e.value.status_code==403


async def test_report_submission_and_owner_acceptance_are_scoped_and_monotonic(data):
    from auth.audit_router import accept_report,update_visit_status
    db,admin,business,_,auditor,_,_=data
    owner={'sub':str(admin),'app_user_id':str(admin),'role':'provider','is_owner':True,'tenant_id':str(admin),'realm_roles':['cb_admin']}
    assigned={'sub':str(auditor),'app_user_id':str(auditor),'role':'provider','is_owner':False,'tenant_id':str(admin),'realm_roles':['auditor']}
    visit=await db.fetchval("INSERT INTO audit_visits(business_tenant,provider_id,auditor_id,visit_type,scheduled_date,status) VALUES($1,$2,$3,'initial',CURRENT_DATE,'completed') RETURNING id",business,admin,auditor)
    with pytest.raises(HTTPException) as e:await update_visit_status(str(visit),{'status':'report_submitted'},user=owner,db=db)
    assert e.value.status_code==403
    await update_visit_status(str(visit),{'status':'report_submitted'},user=assigned,db=db)
    with pytest.raises(HTTPException) as e:await accept_report(str(visit),user=assigned,db=db)
    assert e.value.status_code==403
    accepted=await accept_report(str(visit),user=owner,db=db)
    assert accepted['status']=='report_accepted' and accepted['report_accepted_by']==str(admin)
    with pytest.raises(HTTPException) as e:await accept_report(str(visit),user=owner,db=db)
    assert e.value.status_code==409
    with pytest.raises(HTTPException) as e:await update_visit_status(str(visit),{'status':'completed'},user=owner,db=db)
    assert e.value.status_code==409


async def test_upload_and_submission_bind_to_own_pinned_dossier(data,tmp_path,monkeypatch):
    import io
    from starlette.datastructures import UploadFile,Headers
    from starlette.requests import Request
    from auth import document_router
    from auth.submission_router import SubmitRequest,submit_documents
    db,admin,business,other,_,standard,_=data
    version=await publish(data,[('halal_policy',True)])
    dossier=await db.fetchval("INSERT INTO dossiers(tenant_id,standard_type_id,title,requirements_version_id,requirements_binding_status) VALUES($1,$2,'bound',$3,'bound') RETURNING id",business,standard,version['requirements_version_id'])
    monkeypatch.setattr(document_router,'UPLOAD_DIR',tmp_path)
    def user(uid):return {'sub':str(uid),'app_user_id':str(uid),'email':f'qa-dashboard-{uid}@example.com','role':'business','is_owner':True,'tenant_id':str(uid)}
    def file():return UploadFile(io.BytesIO(b'QA document only. No certification claims.'),filename='qa.txt',headers=Headers({'content-type':'text/plain'}))
    with pytest.raises(HTTPException) as e:await document_router.upload_document(file=file(),doc_type='halal_policy',dossier_id=dossier,user=user(other),db=db)
    assert e.value.status_code==404
    with pytest.raises(HTTPException) as e:await document_router.upload_document(file=file(),doc_type='not_in_requirements',dossier_id=dossier,user=user(business),db=db)
    assert e.value.status_code==422
    uploaded=await document_router.upload_document(file=file(),doc_type='halal_policy',dossier_id=dossier,user=user(business),db=db)
    request=Request({'type':'http','method':'POST','path':'/api/submissions/submit','headers':[],'client':('127.0.0.1',0)})
    submitted=await submit_documents(SubmitRequest(provider_id=str(admin),document_ids=[uploaded['id']]),request,owner=user(business),db=db)
    bound=await db.fetchrow('SELECT requirements_version_id,requirements_binding_status FROM submissions WHERE id=$1',submitted['submission_id'])
    assert str(bound['requirements_version_id'])==version['requirements_version_id'] and bound['requirements_binding_status']=='bound'


async def test_document_inventory_never_returns_ai_based_certification_readiness(data):
    from auth.document_router import dashboard_stats
    db,_,business,_,_,_,_=data
    await db.execute("INSERT INTO documents(filename,original_filename,user_id,tenant_id,doc_type,compliance_score,evaluation_result) VALUES('qa.txt','qa.txt',$1,$1,'halal_policy',100,'{\"overall_status\":\"compliant\"}')",business)
    result=await dashboard_stats(user={'sub':str(business),'app_user_id':str(business),'email':f'qa-dashboard-{business}@example.com','role':'business','is_owner':True,'tenant_id':str(business)},db=db)
    assert 'readiness' not in result and 'compliant_count' not in result and 'total_types' not in result
    assert len(result['doc_type_progress'])==1 and result['avg_score']==100
