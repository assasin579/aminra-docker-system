"""Privileged fixture/proof operations restricted to the current disposable UAT run."""
import json,os,re,subprocess,sys
from pathlib import Path
LABEL='io.aminra.uat.run'

def operation(kind,payload,config=None):
 config=config or json.loads(Path(os.environ['UAT_CONFIG']).read_text())
 run=config['run_id']
 if not re.fullmatch(r'uat-\d{8}-[a-f0-9]{8}',run):raise ValueError('Invalid isolated run')
 name=run+'-backend'
 info=json.loads(subprocess.check_output(['docker','inspect',name],timeout=15))[0]
 if info['Config'].get('Labels',{}).get(LABEL)!=run:raise ValueError('Run ownership mismatch')
 allowed={'member_permissions','legacy_dossier','ai_evidence','audit','suspend_auditor','guard_evidence','actor_state','trust_evidence','authorization_state','set_actor_scope','keycloak_authority','reader_permissions'}
 if kind not in allowed:raise ValueError('Unknown fixture/proof operation')
 code='''import asyncio,json,sys,os,asyncpg
from uuid import UUID,uuid4
m=json.load(sys.stdin);actors=m['actors'];p=m['payload'];kind=m['kind']
async def main():
 c=await asyncpg.connect(os.environ['DATABASE_URL'])
 owner=UUID(actors['bizA']['id']);member=UUID(actors['member']['id'])
 if kind=='member_permissions':
  perms=p['permissions'];assert set(perms)<= {'can_upload','can_edit'} and all(isinstance(v,bool) for v in perms.values())
  n=await c.fetchval("UPDATE users SET permissions=$1::jsonb WHERE id=$2 AND tenant_id=$3 AND NOT is_owner RETURNING id",json.dumps(perms),member,owner);assert n==member
  print(json.dumps({'updated':True}))
 elif kind=='set_actor_scope':
  assert p['actor']=='bizA' and p['tenant'] in ('bizA','bizB') and p['status'] in ('active','suspended') and isinstance(p['is_owner'],bool)
  original_email=actors['bizA']['email'];renamed_email=original_email.replace('@','+renamed@');assert isinstance(p.get('rename_email',False),bool)
  n=await c.fetchval("UPDATE users SET tenant_id=$1,is_owner=$2,status=$3::user_status,email=$6 WHERE id=$4 AND email=ANY($5::text[]) RETURNING id",UUID(actors[p['tenant']]['id']),p['is_owner'],p['status'],owner,[original_email,renamed_email],renamed_email if p.get('rename_email') else original_email);assert n==owner
  print(json.dumps({'updated':True}))
 elif kind=='legacy_dossier':
  standard=UUID(p['standard']);did=uuid4()
  await c.execute("INSERT INTO dossiers (id,tenant_id,standard_type_id,title,status,created_by,requirements_binding_status) VALUES ($1,$2,$3,$4,'draft',$2,'unknown')",did,owner,standard,p['title'])
  print(json.dumps({'id':str(did)}))
 elif kind=='ai_evidence':
  doc=UUID(p['document']);n=await c.fetchval("UPDATE documents SET compliance_score=100,evaluation_result=$1::jsonb WHERE id=$2 AND tenant_id=$3 RETURNING id",json.dumps({'overall_status':'compliant','compliance_score':100,'fixture':'synthetic AI evidence only'}),doc,owner);assert n==doc
  print(json.dumps({'updated':True}))
 elif kind=='suspend_auditor':
  import httpx
  who=p['actor'];assert who in ('assigned','unassigned');a=actors[who];uid=UUID(a['id'])
  assert await c.fetchval('SELECT tenant_id FROM users WHERE id=$1',uid)==UUID(actors['cbX']['id'])
  base='http://uat-keycloak:8080'
  with httpx.Client(timeout=15) as client:
   r=client.post(base+'/realms/master/protocol/openid-connect/token',data={'grant_type':'password','client_id':'admin-cli','username':'uat-admin','password':m['admin_password']});r.raise_for_status();headers={'Authorization':'Bearer '+r.json()['access_token']}
   url=base+'/admin/realms/aminra/users/'+a['id'];r=client.get(url,headers=headers);r.raise_for_status();u=r.json();u.setdefault('attributes',{})['status']=['suspended'];r=client.put(url,headers=headers,json=u);r.raise_for_status()
   r=client.post(base+'/realms/aminra/protocol/openid-connect/token',data={'grant_type':'password','client_id':'aminra-frontend','username':a['email'],'password':a['password']});r.raise_for_status();suspended_token=r.json()['access_token'];import jwt;token_claims=jwt.decode(suspended_token,options={'verify_signature':False});assert token_claims.get('status')=='suspended','UAT realm did not issue the expected suspended status claim'
   u['enabled']=False;r=client.put(url,headers=headers,json=u);r.raise_for_status();r=client.post(url+'/logout',headers=headers);r.raise_for_status()
   login=client.post(base+'/realms/aminra/protocol/openid-connect/token',data={'grant_type':'password','client_id':'aminra-frontend','username':a['email'],'password':a['password']});assert login.status_code==400
  print(json.dumps({'suspended':True,'new_login_denied':True,'access_token':suspended_token}))
 elif kind in ('keycloak_authority','reader_permissions'):
  import httpx
  base='http://uat-keycloak:8080'
  with httpx.Client(timeout=15) as client:
   if kind=='reader_permissions':
    r=client.post(base+'/realms/aminra/protocol/openid-connect/token',data={'grant_type':'client_credentials','client_id':os.environ['KEYCLOAK_AUTHZ_CLIENT_ID'],'client_secret':os.environ['KEYCLOAK_AUTHZ_CLIENT_SECRET']});r.raise_for_status();h={'Authorization':'Bearer '+r.json()['access_token']};url=base+'/admin/realms/aminra/users/'+actors['bizA']['id'];read=client.get(url,headers=h);write=client.put(url,headers=h,json={'enabled':True});print(json.dumps({'read_status':read.status_code,'write_status':write.status_code}))
   else:
    who=p['actor'];assert who in ('admin','assigned');action=p['action'];assert action in ('remove_role','disable','end_session','restore','grant_cb_role');a=actors[who]
    r=client.post(base+'/realms/master/protocol/openid-connect/token',data={'grant_type':'password','client_id':'admin-cli','username':'uat-admin','password':m['admin_password']});r.raise_for_status();h={'Authorization':'Bearer '+r.json()['access_token']};url=base+'/admin/realms/aminra/users/'+a['id']
    role=client.get(base+'/admin/realms/aminra/roles/'+a['role'],headers=h);role.raise_for_status()
    if action in ('remove_role','restore'):
     r=client.request('DELETE' if action=='remove_role' else 'POST',url+'/role-mappings/realm',headers=h,json=[role.json()]);r.raise_for_status()
    if who=='admin' and action in ('grant_cb_role','restore'):
     cb=client.get(base+'/admin/realms/aminra/roles/cb_admin',headers=h);cb.raise_for_status();r=client.request('POST' if action=='grant_cb_role' else 'DELETE',url+'/role-mappings/realm',headers=h,json=[cb.json()]);r.raise_for_status()
    if action in ('disable','restore'):

     r=client.put(url,headers=h,json={'enabled':action=='restore'});r.raise_for_status()
    if action=='end_session':
     r=client.post(url+'/logout',headers=h);r.raise_for_status()
    print(json.dumps({'updated':True}))
 elif kind=='audit':
  doc=UUID(p['document']);assert await c.fetchval('SELECT tenant_id FROM documents WHERE id=$1',doc)==owner
  rows=await c.fetch("SELECT action,metadata FROM audit_logs WHERE entity_id=$1 ORDER BY created_at",str(doc));print(json.dumps([{'action':r['action'],'metadata':json.loads(r['metadata']) if isinstance(r['metadata'],str) else r['metadata']} for r in rows],default=str))
 elif kind=='trust_evidence':
  provider=UUID(actors['cbX']['id']);entity=UUID(p['id'])
  if p['entity']=='complaint':
   assert await c.fetchval('SELECT id FROM complaint_cases WHERE id=$1 AND provider_id=$2 AND business_tenant=$3',entity,provider,owner)==entity
   events=await c.fetch('SELECT event_type,from_status,to_status,actor_user_id FROM complaint_case_events WHERE case_id=$1 ORDER BY created_at,id',entity)
   extra={'events':[dict(row) for row in events]}
  else:
   assert p['entity']=='conflict'
   assert await c.fetchval('SELECT id FROM conflict_declarations WHERE id=$1 AND provider_id=$2 AND business_tenant=$3',entity,provider,owner)==entity
   overrides=await c.fetch('SELECT overridden_by,override_reason FROM conflict_overrides WHERE declaration_id=$1 ORDER BY created_at,id',entity)
   extra={'overrides':[dict(row) for row in overrides]}
  logs=await c.fetch('SELECT action,user_id FROM audit_logs WHERE entity_id=$1 ORDER BY created_at,id',str(entity))
  print(json.dumps({**extra,'audit':[dict(row) for row in logs]},default=str))
 elif kind=='authorization_state':
  document=UUID(p['document']);visit=UUID(p['visit'])
  doc=await c.fetchrow('SELECT tenant_id FROM documents WHERE id=$1 AND tenant_id=$2',document,owner);assert doc
  audit=await c.fetchrow('SELECT provider_id FROM audit_visits WHERE id=$1 AND provider_id=$2',visit,UUID(actors['cbX']['id']));assert audit
  selector=await c.fetchval('SELECT selected_by FROM document_current_versions WHERE current_document_id=$1 AND tenant_id=$2',document,owner)
  print(json.dumps({'selected_by':selector,'document_tenant':doc['tenant_id'],'provider_id':audit['provider_id']},default=str))
 elif kind=='actor_state':
  sub=await c.fetchrow('SELECT id,auditor_id,provider_id,document_ids FROM submissions WHERE id=$1 AND business_tenant=$2',UUID(p['submission']),owner)
  rows=await c.fetch('SELECT id,is_owner,status,tenant_id FROM users WHERE id=ANY($1::uuid[])',[UUID(actors[x]['id']) for x in ('assigned','unassigned','cbX')])
  print(json.dumps({'submission':dict(sub),'actors':[dict(r) for r in rows]},default=str))
 elif kind=='guard_evidence':
  expected={}
  for key,sql,args in [
   ('attachment_update',"UPDATE dossier_document_attachments SET doc_type=doc_type WHERE dossier_id=$1",[UUID(p['dossier'])]),
   ('attachment_delete',"DELETE FROM dossier_document_attachments WHERE dossier_id=$1",[UUID(p['dossier'])]),
   ('requirements_update',"UPDATE standard_requirement_version_slots SET required=NOT required WHERE requirements_version_id=$1",[UUID(p['requirements'])]),
   ('round_update',"UPDATE submission_revision_requests SET submitted_document_ids=ARRAY[]::uuid[] WHERE submission_id=$1",[UUID(p['submission'])])]:
   tx=c.transaction();await tx.start()
   try:await c.execute(sql,*args);expected[key]=False
   except asyncpg.PostgresError as e:expected[key]=e.sqlstate in ('42501','P0001','23514','55000')
   finally:await tx.rollback()
  print(json.dumps(expected))
 await c.close()
asyncio.run(main())'''
 r=subprocess.run(['docker','exec','-i',name,'python','-c',code],input=json.dumps({'kind':kind,'actors':config['actors'],'payload':payload,'admin_password':config.get('keycloak_admin_password')}),text=True,capture_output=True,timeout=60)
 if r.returncode:raise RuntimeError('Scoped fixture/proof failed: '+r.stderr[-800:])
 return json.loads(r.stdout)
if __name__=='__main__':print(json.dumps(operation(sys.argv[1],json.load(sys.stdin))))
