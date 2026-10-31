import {test,expect} from '@playwright/test';
import {randomUUID,createHash} from 'node:crypto';
import {api,attach,config,control,expand,login,makeDossier,packet,pdf,prepare,token} from './helpers';

for(const variant of ['unpublished','legacy','optional','missing'] as const){
 test(`J1-READINESS-${variant} @DOS-03 @DOS-04 @DOS-07 unknown and missing requirements never imply completion`,async({page,request},info)=>{
  const f=await prepare(request,'readiness-'+variant,[{doc_type:'halal_policy',required:variant!=='optional',display_order:0}],variant!=='unpublished');
  const d=variant==='legacy'?control('legacy_dossier',{standard:f.standard.id,title:f.name}):await makeDossier(request,f,variant);
  const r=await api(request,f.biz,'/dossiers/'+d.id+'/readiness');
  if(variant==='missing'){expect(r.missing_required_documents).toContain('halal_policy');expect(r.readiness_percent).toBe(0);}
  else{expect(r.readiness_percent).toBeNull();expect(r.state).toBe({unpublished:'requirements_unconfigured',legacy:'requirements_unknown',optional:'requirements_no_required_slots'}[variant]);}
  expect(r.certificate_issue_blocked).toBe(true);await login(page,'bizA');await page.goto('/dossiers/'+d.id);await expect(page.getByRole('heading',{name:variant==='legacy'?f.name:f.name+' '+variant,exact:true})).toBeVisible();
  if(variant==='missing')await expect(page.getByLabel('Sẵn sàng 0 phần trăm',{exact:true})).toBeVisible();else await expect(page.getByLabel('Chưa xác định mức sẵn sàng',{exact:true})).toBeVisible();
  await info.attach('readiness-ui',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});await info.attach('readiness-contract',{body:JSON.stringify(r),contentType:'application/json'});
 });
}

test('J1-REUSE @DOS-02 @DOC-05 exact document reuse does not borrow another dossier review context',async({page,request})=>{
 const f=await prepare(request,'reuse'),a=await makeDossier(request,f,'source'),b=await makeDossier(request,f,'target');const doc=await attach(request,f.biz,a.id,f.name+'.pdf');await login(page,'bizA');await page.goto('/dossiers/'+b.id);await page.getByLabel('Tài liệu có sẵn cho Chính sách Halal').selectOption(doc);
 const[reused]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/dossiers/'+b.id+'/documents')&&r.request().method()==='POST'),page.getByRole('button',{name:'Đính kèm tài liệu',exact:true}).click()]);expect(reused.status()).toBe(200);expect((await reused.json()).document_id).toBe(doc);
 const ra=await api(request,f.biz,'/dossiers/'+a.id+'/readiness'),rb=await api(request,f.biz,'/dossiers/'+b.id+'/readiness');expect(ra.requirement_slots[0].evidence_document_id).toBe(doc);expect(rb.requirement_slots[0].evidence_document_id).toBe(doc);expect(rb.submission_round).toBeNull();
 const foreign=await token(request,'bizB');const denied=await request.post(config.base_url+'/api/dossiers/'+b.id+'/documents',{headers:{Authorization:'Bearer '+foreign,'Idempotency-Key':randomUUID()},multipart:{doc_type:'halal_policy',document_id:doc}});expect(denied.status()).toBe(404);
 // The API-only foreign-token probe does not switch this browser's actor.
 // Verify the existing business session and reload the dossier; repeated
 // authenticated login-page navigation belongs to the auth lifecycle suite.
 await page.goto('/dossiers/'+b.id);await expect(page.getByRole('button').filter({hasText:config.actors.bizA.email}).first()).toBeVisible();await expect(page.getByTestId('doc-type-row-halal_policy')).toContainText('1 file đã upload');
});

test('J1-AI-NOT-APPROVAL @DOS-05 @DOS-08 AI score alone cannot make a dossier certified',async({page,request})=>{
 const f=await prepare(request,'ai-only'),d=await makeDossier(request,f,'AI');const doc=await attach(request,f.biz,d.id,f.name+'.pdf');control('ai_evidence',{document:doc});
 const r=await api(request,f.biz,'/dossiers/'+d.id+'/readiness');expect(r.readiness_percent).toBe(0);expect(r.certificate_issue_blocked).toBe(true);expect(r.requirement_slots[0].evidence_document_id).toBe(doc);expect(r.requirement_slots[0].state).toBe('ready_to_submit');
 await login(page,'bizA');await page.goto('/dossiers/'+d.id);await expect(page.getByText('Gửi hồ sơ cho đơn vị chứng nhận',{exact:true})).toBeVisible();
});

test('J1-PACKET-PREVIEW @CB-05 @DOC-07 selected CB sees packet and file while foreign CB and business are denied',async({browser,request},info)=>{
 const f=await packet(request,'preview'),cb=await token(request,'cbX'),foreign=await token(request,'cbY'),other=await token(request,'bizB');
 const ctx=await browser.newContext({viewport:{width:1440,height:1000}});try{const p=await ctx.newPage();await login(p,'cbX');await expand(p,'cbX',f.submission);await expect(p.getByText(f.name,{exact:true}).first()).toBeVisible();
 const preview=await request.get(config.base_url+'/api/api/documents/'+f.document+'/preview',{headers:{Authorization:'Bearer '+cb}});expect(preview.status()).toBe(200);
 const download=await request.get(config.base_url+'/api/api/documents/'+f.document+'/file',{headers:{Authorization:'Bearer '+cb}});expect(download.status()).toBe(200);expect(createHash('sha256').update(await download.body()).digest('hex')).toBe(createHash('sha256').update(pdf(f.name)).digest('hex'));
 for(const actor of [foreign,other])for(const suffix of ['preview','file']){const r=await request.get(config.base_url+'/api/api/documents/'+f.document+'/'+suffix,{headers:{Authorization:'Bearer '+actor}});expect(r.status()).toBe(404);}
 await info.attach('selected-cb-packet',{body:await p.screenshot({fullPage:true}),contentType:'image/png'});
 }finally{await ctx.close();}
});

test('J1-DASHBOARD-RACE @AUTH-04 @DOS-07 delayed previous-tenant dashboard cannot populate the new account',async({page,request},info)=>{
 const lifecycle: unknown[] = [];
 page.on('console', message => { if (message.type() === 'debug' && message.text().startsWith('auth-probe:')) lifecycle.push(JSON.parse(message.text().slice(11))); });
 await page.addInitScript(() => {
  const record = (event: string, detail: Record<string, unknown> = {}) => console.debug('auth-probe:' + JSON.stringify({event, path: location.pathname, at: performance.now(), ...detail}));
  for (const event of ['beforeunload', 'pagehide', 'pageshow', 'DOMContentLoaded']) window.addEventListener(event, () => record(event));
  const remove = Storage.prototype.removeItem;
  Storage.prototype.removeItem = function(key) { if (key === 'aminra_user_token') record('credential_removed', {stack: new Error().stack}); return remove.call(this, key); };
  const set = Storage.prototype.setItem;
  Storage.prototype.setItem = function(key, value) { if (key === 'aminra_user_token') record('credential_saved'); if (key === 'aminra_auth_last_purge_reason') record('purge', {reason: value}); return set.call(this, key, value); };
 });
 const f=await prepare(request,'dashboard',undefined,false);await makeDossier(request,f,'private');
 const b=await token(request,'bizB'),bProfile=await api(request,b,'/auth/me');if(!bProfile.industry_schema_id){const aProfile=await api(request,f.biz,'/auth/me');await api(request,b,'/industry-schemas/business-select','POST',{schema_id:aProfile.industry_schema_id});}
 const bEmpty=await api(request,b,'/dossiers/dashboard');expect(bEmpty.total_dossiers).toBe(0);expect(bEmpty.profiles).toEqual([]);
 await login(page,'bizA');await page.goto('/dashboard/business');
 let release!:()=>void,settle!:()=>void;const held=new Promise<void>(r=>release=r),settled=new Promise<void>(r=>settle=r);let responseHeld=false;
 // Auth restoration/refresh may issue more than one request. Delay every
 // request from actor A, while allowing actor B's own request to complete.
 // Decoding here identifies test traffic only; the backend still verifies it.
 await page.route('**/api/dossiers/dashboard?*',async route=>{
  let subject:string|undefined;
  try{subject=JSON.parse(Buffer.from((route.request().headers().authorization||'').replace(/^Bearer /,'').split('.')[1]||'','base64url').toString()).sub;}catch{/* anonymous traffic is not the race fixture */}
  if(subject!==config.actors.bizA.id)return route.continue();
  const response=await route.fetch();expect(response.headers()['cache-control']).toContain('no-store');responseHeld=true;await held;try{await route.fulfill({response});}catch{/* navigation may cancel the old response */}finally{settle();}
 });
 try{await page.reload({waitUntil:'domcontentloaded'});await expect.poll(()=>({held:responseHeld,path:new URL(page.url()).pathname}),{timeout:15000,message:'Session restore must retain the business dashboard and intercept a response before account-switch assertions'}).toMatchObject({held:true,path:'/dashboard/business'});await expect(page.getByText('Đang tải mức sẵn sàng hồ sơ…',{exact:true})).toBeVisible();await page.getByRole('button').filter({hasText:config.actors.bizA.email}).first().click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();await login(page,'bizB');release();await settled;await page.waitForLoadState('networkidle');await expect(page.getByRole('heading',{name:'Bắt đầu hồ sơ chứng nhận',exact:true})).toBeVisible();await expect(page.locator('body')).not.toContainText(f.name+' private');await info.attach('account-race',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});}finally{release();await info.attach('auth-lifecycle',{body:JSON.stringify(lifecycle),contentType:'application/json'});}
});

test('[API] J2-AUTHORITY @SUB-05 @CB-03 @E2E-12 correction authority and history follow exact auditor assignment',async({request})=>{
 const f=await packet(request,'authority'),cb=await token(request,'cbX'),assigned=await token(request,'assigned'),unassigned=await token(request,'unassigned'),member=await token(request,'member'),foreign=await token(request,'cbY');
 await api(request,cb,'/api/submissions/received/'+f.submission+'/assign','PUT',{auditor_id:config.actors.assigned.id});
 const path='/api/submissions/received/'+f.submission+'/request-revision';
 for(const t of [member,foreign,unassigned]){const r=await request.post(config.base_url+'/api'+path,{headers:{Authorization:'Bearer '+t,'Idempotency-Key':randomUUID()},data:{feedback:'must be denied'}});expect([403,404]).toContain(r.status());}
 await api(request,cb,'/api/submissions/received/'+f.submission+'/status','PUT',{status:'reviewing'});
 await api(request,assigned,path,'POST',{feedback:f.name+' exact assignment'});
 for(const t of [f.biz,member,cb,assigned]){const history=await api(request,t,'/api/submissions/'+f.submission+'/revisions');expect(JSON.stringify(history)).toContain(f.name+' exact assignment');}
 for(const t of [foreign,unassigned]){const r=await request.get(config.base_url+'/api/api/submissions/'+f.submission+'/revisions',{headers:{Authorization:'Bearer '+t}});expect([403,404]).toContain(r.status());}
});

test('[API] J2-FILE-REASSIGN @CB-04 @DOC-07 historic bytes require current assignment and active auditor',async({request})=>{
 const f=await packet(request,'reassign'),cb=await token(request,'cbX'),old=await token(request,'assigned'),next=await token(request,'unassigned');const file=config.base_url+'/api/api/documents/'+f.document+'/file';
 await api(request,cb,'/api/submissions/received/'+f.submission+'/assign','PUT',{auditor_id:config.actors.assigned.id});expect((await request.get(file,{headers:{Authorization:'Bearer '+old}})).status()).toBe(200);
 await api(request,cb,'/api/submissions/received/'+f.submission+'/assign','PUT',{auditor_id:config.actors.unassigned.id});const oldResponse=await request.get(file,{headers:{Authorization:'Bearer '+old}});
 const diagnostic=control('actor_state',{submission:f.submission});
 const direct=await request.get(config.api_url+'/api/documents/'+f.document+'/file',{headers:{Authorization:'Bearer '+old}});
 expect(oldResponse.status(),JSON.stringify({db:diagnostic,direct_status:direct.status()})).toBe(404);expect((await request.get(file,{headers:{Authorization:'Bearer '+next}})).status()).toBe(200);
 // Assignment, application suspension and identity revocation are distinct
 // authority boundaries. Do not conflate all refusals into a document 404.
 const assertDenied=async(t:string,status:number)=>{
  for(const url of [file,config.api_url+'/api/documents/'+f.document+'/file']){
   const response=await request.get(url,{headers:{Authorization:'Bearer '+t}});
   expect(response.status()).toBe(status);
   expect(response.headers()['content-type']).toContain('application/json');
   const body=await response.body();expect(body.includes(Buffer.from('%PDF'))).toBe(false);
   expect(body.toString()).not.toContain(f.name);
  }
 };
 await assertDenied(old,404);
 expect(control('suspend_auditor',{actor:'unassigned',mode:'application',status:'suspended'}).status).toBe('suspended');
 await assertDenied(next,403);
 expect(control('suspend_auditor',{actor:'unassigned',mode:'application',status:'active'}).status).toBe('active');
 expect((await request.get(file,{headers:{Authorization:'Bearer '+next}})).status()).toBe(200);
 const revoked=control('suspend_auditor',{actor:'unassigned',mode:'identity'});
 expect(revoked.new_login_denied).toBe(true);await assertDenied(revoked.access_token,401);
 expect((await request.get(file,{headers:{Authorization:'Bearer '+cb}})).status()).toBe(200);
});

test('[API] X-PUBLICATION-GUARDS @STD-02 @STD-03 @SUB-03 only platform admin publishes and immutable evidence rejects edits',async({request})=>{
 const f=await packet(request,'immutable'),cb=await token(request,'cbX');
 for(const t of [f.biz,cb]){const r=await request.post(config.base_url+'/api/auth/admin/standard-types/'+f.standard.id+'/publish-requirements',{headers:{Authorization:'Bearer '+t}});expect(r.status()).toBe(403);}
 await api(request,cb,'/api/submissions/received/'+f.submission+'/status','PUT',{status:'reviewing'});await api(request,cb,'/api/submissions/received/'+f.submission+'/request-revision','POST',{feedback:'Immutable round'});
 const r=await api(request,f.biz,'/dossiers/'+f.dossier+'/readiness');const guards=control('guard_evidence',{dossier:f.dossier,requirements:r.requirements_version_id,submission:f.submission});expect(guards).toEqual({attachment_update:true,attachment_delete:true,requirements_update:true,round_update:true});
});

test('J2-MEMBER-HISTORY @SUB-05 @SUB-06 @ORG-04 member reads exact CB feedback without replace or resubmit commands',async({page,request})=>{
 const f=await packet(request,'member-history'),cb=await token(request,'cbX');await api(request,cb,'/api/submissions/received/'+f.submission+'/status','PUT',{status:'reviewing'});await api(request,cb,'/api/submissions/received/'+f.submission+'/request-revision','POST',{feedback:f.name+' correction',document_feedback:[{document_id:f.document,issue:'Synthetic old-version issue',severity:'major',suggestion:'Replace evidence'}]});
 const newName=f.name.replace('.pdf','-replacement.pdf');const upload=await request.post(config.base_url+'/api/api/documents/upload',{headers:{Authorization:'Bearer '+f.biz},multipart:{doc_type:'halal_policy',file:{name:newName,mimeType:'application/pdf',buffer:pdf(newName)}}});expect(upload.status()).toBe(200);const next=(await upload.json()).id;
 await api(request,f.biz,'/api/submissions/received/'+f.submission+'/replace-document','PUT',{old_doc_id:f.document,new_doc_id:next});await api(request,f.biz,'/api/submissions/'+f.submission+'/resubmit','POST',{business_notes:'Retained response after replacement'});
 const member=await login(page,'member');await page.goto('/dossiers/'+f.dossier);await expect(page.locator('[data-revision-panel]')).toContainText(f.name+' correction');const historicalIssue=page.locator('[data-revision-panel] li').filter({hasText:'Synthetic old-version issue'});await expect(historicalIssue).toContainText(f.name);await expect(historicalIssue).not.toContainText(newName);await expect(page.locator('[data-revision-panel]')).toContainText('Retained response after replacement');await expect(page.getByRole('button',{name:'Đính kèm tài liệu',exact:true})).toHaveCount(0);await expect(page.locator('[data-form="resubmit"]')).toHaveCount(0);await expect(page.getByTitle('Thay bằng phiên bản mới',{exact:true})).toHaveCount(0);
 const denied=await request.post(config.base_url+'/api/api/submissions/'+f.submission+'/resubmit',{headers:{Authorization:'Bearer '+member},data:{business_notes:'denied'}});expect(denied.status()).toBe(403);
});

test('J1-DELEGATED-UPLOAD @ORG-04 @DOS-02 delegated upload is effective and revocation removes the capability',async({page,request})=>{
 const f=await prepare(request,'delegated'),d=await makeDossier(request,f,'delegated');control('member_permissions',{permissions:{can_upload:true}});
 try{
  await login(page,'member');await page.goto('/dossiers/'+d.id);await page.getByLabel('Tệp mới cho Chính sách Halal').setInputFiles({name:f.name+'.pdf',mimeType:'application/pdf',buffer:pdf(f.name)});
  const[attached]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/dossiers/'+d.id+'/documents')&&r.request().method()==='POST'),page.getByRole('button',{name:'Đính kèm tài liệu',exact:true}).click()]);expect(attached.status()).toBe(200);await expect(page.getByTestId('dossier-submit-cta')).toHaveCount(0);
 }finally{control('member_permissions',{permissions:{can_upload:false}});}
 await page.reload();await expect(page.getByRole('button',{name:'Đính kèm tài liệu',exact:true})).toHaveCount(0);
});

test('AUTH-NAVIGATION @AUTH-04 reload during profile restoration preserves the credential and verifies it again',async({page,request},info)=>{
 await prepare(request,'navigation',undefined,false);
 await login(page,'bizA');
 let release!:()=>void;const held=new Promise<void>(resolve=>release=resolve);let captured=false;
 await page.route('**/api/auth/me',async route=>{
  if(captured)return route.continue();
  const response=await route.fetch();expect(response.status()).toBe(200);captured=true;
  await held;try{await route.fulfill({response});}catch{/* the departing document cancels this response */}
 });
 try{
  await page.goto('/dashboard/business');
  await expect.poll(()=>captured).toBe(true);
  await page.reload({waitUntil:'domcontentloaded'});release();
  await expect(page.getByRole('button').filter({hasText:config.actors.bizA.email}).first()).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/dashboard/business');
  const state=await page.evaluate(()=>({credentialPresent:!!localStorage.getItem('aminra_user_token'),purge:sessionStorage.getItem('aminra_auth_last_purge_reason')}));
  expect(state).toEqual({credentialPresent:true,purge:null});
  await info.attach('navigation-restore',{body:JSON.stringify(state),contentType:'application/json'});
 }finally{release();}
});

for(const [kind,actor] of [['business','bizA'],['provider','cbX']] as const){
 test(`AUTH-HYDRATION-${kind} @AUTH-01 @AUTH-02 server controls stay inert until handlers attach, then native login succeeds`,async({page,request})=>{
  if(kind==='business')await prepare(request,'hydration',undefined,false);
  let release!:()=>void;const scripts=new Promise<void>(resolve=>release=resolve);
  await page.route('**/_next/static/**/*.js',async route=>{await scripts;await route.continue();});
  try{
   await page.goto('/'+kind+'/login',{waitUntil:'commit'});
   await expect(page.locator('input[type=email]')).toBeDisabled();await expect(page.locator('input[type=password]')).toBeDisabled();
   release();await expect(page.locator('input[type=email]')).toBeEnabled();
   const a=config.actors[actor];await page.locator('input[type=email]').fill(a.email);await page.locator('input[type=password]').fill(a.password);
   const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/auth/login')&&r.request().method()==='POST'),page.getByRole('button',{name:'Đăng nhập',exact:true}).click()]);
   expect(response.status()).toBe(200);await page.waitForURL('**/dashboard/'+kind);
   await expect(page.getByRole('button').filter({hasText:a.email}).first()).toBeVisible();
  }finally{release();}
 });
}


test.describe('first service-worker claim',()=>{
 test.use({serviceWorkers:'allow'});
 for(const [kind,actor] of [['business','bizA'],['provider','cbX']] as const){
  test(`PWA-FIRST-CLAIM-${kind} @AUTH-01 @AUTH-04 native login survives actual worker activation without document reload`,async({page,request},info)=>{
   if(kind==='business')await prepare(request,'pwa-claim',undefined,false);
   const navigations:string[]=[];
   page.on('request',r=>{if(r.isNavigationRequest()&&r.frame()===page.mainFrame())navigations.push(new URL(r.url()).pathname);});
   await login(page,actor);
   await expect.poll(()=>page.evaluate(()=>!!navigator.serviceWorker.controller)).toBe(true);
   await expect(page.getByRole('button').filter({hasText:config.actors[actor].email}).first()).toBeVisible();
   expect(navigations).toEqual(['/'+kind+'/login']);
   const state=await page.evaluate(()=>({credential:!!localStorage.getItem('aminra_user_token'),purge:sessionStorage.getItem('aminra_auth_last_purge_reason')}));
   expect(state).toEqual({credential:true,purge:null});
   await info.attach('actual-worker-first-claim',{body:JSON.stringify({navigations,state}),contentType:'application/json'});
  });
 }
});


test('RECIPIENT-01 @SUB-01 @CB-05 business sent card identifies the actual selected receiving CB',async({page,request},info)=>{
 const f=await packet(request,'recipient');
 const list=await api(request,f.biz,'/api/submissions/my-submissions');
 const sent=list.submissions.find((s:{id:string})=>s.id===f.submission);
 expect(sent.provider_name).toBe(config.actors.cbX.email.split('@')[0]);
 expect(sent.provider_email).toBe(config.actors.cbX.email);
 await login(page,'bizA');await page.goto('/submissions');
 const card=page.locator('[data-submission-id="'+f.submission+'"]');
 await expect(card.getByText('Tổ chức tiếp nhận',{exact:true})).toBeVisible();
 await expect(card.getByText(sent.provider_name,{exact:true})).toBeVisible();
 await expect(card.getByText('Email liên hệ: '+sent.provider_email,{exact:true})).toBeVisible();
 await info.attach('sent-recipient',{body:await card.screenshot(),contentType:'image/png'});
});


test('STANDARD-REQUIRED-01 @STD-01 @DOS-03 @SUB-01 workspace dossier requires both admin-defined document types before send',async({page,request})=>{
 const f=await prepare(request,'two-required-types',[{doc_type:'halal_policy',required:true,display_order:0},{doc_type:'has_manual',required:true,display_order:1}]);
 const dossier=await makeDossier(request,f,'two required');
 const policy=await attach(request,f.biz,dossier.id,f.name+'-policy.pdf');
 await api(request,f.biz,'/api/documents/'+policy+'/promote','POST');
 await login(page,'bizA');await page.goto('/dossiers/'+dossier.id);
 await expect(page.locator('[data-document-workspace]').getByRole('link',{name:'Các bộ hồ sơ',exact:true})).toHaveAttribute('aria-current','page');
 await expect(page.getByTestId('dossier-submit-cta')).toHaveCount(0);
 const before=await api(request,f.biz,'/api/submissions/my-submissions');
 const denied=await request.post(config.base_url+'/api/api/submissions/submit',{headers:{Authorization:'Bearer '+f.biz},data:{provider_id:config.actors.cbX.id,dossier_id:dossier.id,document_ids:[policy]}});
 expect(denied.status()).toBe(400);expect((await denied.json()).detail).toContain('has_manual');
 expect((await api(request,f.biz,'/api/submissions/my-submissions')).submissions.length).toBe(before.submissions.length);
 const uploaded=await request.post(config.base_url+'/api/dossiers/'+dossier.id+'/documents',{headers:{Authorization:'Bearer '+f.biz,'Idempotency-Key':randomUUID()},multipart:{doc_type:'has_manual',file:{name:f.name+'-manual.pdf',mimeType:'application/pdf',buffer:pdf(f.name+' manual')}}});expect(uploaded.status()).toBe(200);const manual=(await uploaded.json()).document_id;
 await api(request,f.biz,'/api/documents/'+manual+'/promote','POST');
 await page.reload();await page.getByTestId('dossier-submit-cta').click();await page.waitForURL('**/submissions?dossier_id='+dossier.id);
 await page.getByRole('button',{name:'Gửi hồ sơ mới',exact:true}).click();const modal=page.getByRole('dialog');
 await expect(modal.getByRole('checkbox')).toHaveCount(2);
 await modal.getByRole('button').filter({hasText:config.actors.cbX.email.split('@')[0]}).click();
 const manualBox=modal.getByRole('checkbox',{name:new RegExp(f.name+'-manual.pdf')});await manualBox.uncheck();await expect(modal.getByRole('button',{name:'Gửi 1 tài liệu',exact:true})).toBeDisabled();await manualBox.check();
 const [sent]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/submissions/submit')&&r.request().method()==='POST'),modal.getByRole('button',{name:'Gửi 2 tài liệu',exact:true}).click()]);expect(sent.status()).toBe(200);
 const body=await sent.json();const rows=await api(request,f.biz,'/api/submissions/my-submissions');const submitted=rows.submissions.find((row:{id:string})=>row.id===body.submission_id);expect([...submitted.document_ids].sort()).toEqual([policy,manual].sort());
});
