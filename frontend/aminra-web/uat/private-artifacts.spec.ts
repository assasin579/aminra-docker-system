import { test, expect } from '@playwright/test';
import { api, config, control, packet, token, pdf } from './helpers';

test('[API] PRIVATE-REVIEW-SCOPE @AUTH-06 @DAT-01 @E2E-12 same filename never shares reviews between principals',async({request})=>{
 const a=await token(request,'bizA'),b=await token(request,'bizB'),member=await token(request,'member');const name=config.run_id+'-same-file.pdf';
 const path='/reviews/'+name;
 const review={filename:name,reviewer:'Synthetic A',notes:'Private synthetic A review',status:'pending',confirmed_issues:[],false_positives:[],additional_findings:[],issue_comments:{}};
 await api(request,a,path,'POST',review);
 for(const t of [b,member]){const missing=await api(request,t,path);expect(missing.exists).toBe(false);expect(JSON.stringify(missing)).not.toContain(review.notes);}
 await api(request,b,path,'POST',{...review,notes:'Private synthetic B review'});
 expect((await api(request,a,path)).review.notes).toBe(review.notes);
 expect((await api(request,b,path)).review.notes).toBe('Private synthetic B review');
});

test('[API] PRINCIPAL-REVOCATION @AUTH-05 @ORG-04 old mapper claims cannot restore tenant, ownership or account activity',async({request})=>{
 const f=await packet(request,'revocation');
 try{
  control('set_actor_scope',{actor:'bizA',tenant:'bizB',is_owner:false,status:'active'});
  const me=await api(request,f.biz,'/auth/me');expect(me.tenant_id).toBe(config.actors.bizB.id);expect(me.is_owner).toBe(false);
  const oldFile=await request.get(config.base_url+`/api/api/documents/${f.document}/file`,{headers:{Authorization:'Bearer '+f.biz}});expect(oldFile.status()).toBe(404);
  control('set_actor_scope',{actor:'bizA',tenant:'bizB',is_owner:false,status:'suspended',rename_email:true});
  for(const path of ['/auth/me',`/api/documents/${f.document}/file`]){const denied=await request.get(config.base_url+'/api'+path,{headers:{Authorization:'Bearer '+f.biz}});expect(denied.status(),await denied.text()).toBe(403);}
 }finally{control('set_actor_scope',{actor:'bizA',tenant:'bizA',is_owner:true,status:'active'});}
});

test('[API] PRIVATE-JOB-AND-INGEST @DAT-01 @E2E-12 regular users cannot publish private documents to shared knowledge or read unbound jobs',async({request})=>{
 for(const actor of ['bizA','bizB','cbX','assigned'] as const){
  const t=await token(request,actor);const headers={Authorization:'Bearer '+t};
  const ingest=await request.post(config.base_url+'/api/ingest',{headers,multipart:{file:{name:'private.pdf',mimeType:'application/pdf',buffer:pdf('Private must not enter shared corpus')}}});expect(ingest.status(),await ingest.text()).toBe(403);
  const job=await request.get(config.base_url+'/api/jobs/00000000-0000-0000-0000-000000000001',{headers});expect(job.status(),await job.text()).toBe(404);
 }
 const admin=await token(request,'admin');
 const queued=await request.post(config.base_url+'/api/ingest',{headers:{Authorization:'Bearer '+admin},multipart:{file:{name:config.run_id+'-public-reference.pdf',mimeType:'application/pdf',buffer:pdf('Synthetic reviewed public reference')}}});
 expect(queued.status(),await queued.text()).toBe(200);const job=await queued.json();expect(job.status).toBe('queued');
 expect((await api(request,admin,'/jobs/'+job.job_id)).status).toBe('queued');
 for(const actor of ['bizA','cbX'] as const){const other=await token(request,actor);const denied=await request.get(config.base_url+'/api/jobs/'+job.job_id,{headers:{Authorization:'Bearer '+other}});expect(denied.status()).toBe(404);}
});

test('[API] PRIVATE-CACHE-HEADERS @AUTH-04 @DAT-01 authenticated identity and files are never reusable shared cache entries',async({request})=>{
 const f=await packet(request,'cache-headers');
 for(const path of ['/auth/me',`/api/documents/${f.document}/file`]){
  const r=await request.get(config.base_url+'/api'+path,{headers:{Authorization:'Bearer '+f.biz}});expect(r.status()).toBe(200);
  expect(r.headers()['cache-control']).toContain('no-store');expect(r.headers()['vary'].toLowerCase()).toContain('authorization');
 }
});


test('[API] KEYCLOAK-LIVE-AUTHORITY @AUTH-05 @CB-05 role removal, account disable and session logout revoke existing tokens across entry points',async({request},info)=>{
 const reader=control('reader_permissions',{});expect(reader.read_status).toBe(200);expect(reader.write_status).toBe(403);
 const admin=await token(request,'admin');expect((await api(request,admin,'/admin/verify')).valid).toBe(true);
 try{
  control('keycloak_authority',{actor:'admin',action:'remove_role'});
  await expect.poll(async()=>{const r=await request.get(config.base_url+'/api/auth/me',{headers:{Authorization:'Bearer '+admin}});return r.status();},{timeout:10000}).toBe(401);
  expect((await api(request,admin,'/admin/verify')).valid).toBe(false);
  const query=await request.get(config.base_url+'/api/admin/templates/halal_policy/template-file/view',{params:{token:admin}});expect(query.status()).toBe(401);
 }finally{control('keycloak_authority',{actor:'admin',action:'restore'});}
 for(const action of ['disable','end_session']){
  const staff=await token(request,'assigned');await api(request,staff,'/auth/me');
  try{
   control('keycloak_authority',{actor:'assigned',action});
   await expect.poll(async()=>{const r=await request.get(config.base_url+'/api/auth/me',{headers:{Authorization:'Bearer '+staff}});return r.status();},{timeout:10000}).toBe(401);
  }finally{control('keycloak_authority',{actor:'assigned',action:'restore'});}
 }
 await info.attach('runtime-reader-scope',{body:JSON.stringify({...reader,cache_ttl_seconds:2,production_max_ttl_seconds:30,revocation_target_seconds:60}),contentType:'application/json'});
});
