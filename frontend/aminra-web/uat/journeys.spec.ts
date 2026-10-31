import fs from 'node:fs';
import crypto from 'node:crypto';
import {test,expect} from '@playwright/test';
import {api,config,expand,login,pdf,prepare,token} from './helpers';

test('JOURNEY-01 @DOS-01 @DOS-02 @SUB-01 @SUB-02 @SUB-03 @SUB-05 @SUB-06 @SUB-08 @DOC-05 @E2E-02 @E2E-13 browser submission, lost response, correction and retained evidence',async({browser,request},info)=>{
 const fixture=await prepare(request,'journey');const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
 const cbContext=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
 try{
 const p=await context.newPage(),q=await cbContext.newPage();const errors:string[]=[];p.on('pageerror',e=>errors.push(e.message));q.on('pageerror',e=>errors.push(e.message));
 await login(p,'bizA');await p.goto('/dossiers/new');await p.getByTestId('dossier-title-input').fill(fixture.name);
 await p.getByTestId('standard-option-'+fixture.standard.code).click();
 const[created]=await Promise.all([p.waitForResponse(r=>r.url().endsWith('/api/dossiers')&&r.request().method()==='POST'),p.getByTestId('dossier-create-submit').click()]);
 expect(created.status(),await created.text()).toBe(201);const dossier=(await created.json()).id;await p.waitForURL('**/dossiers/'+dossier);
 const oldName=fixture.name+'-old.pdf',newName=fixture.name+'-new.pdf';const bytes=pdf(fixture.name);
 await p.getByLabel('Tệp mới cho Chính sách Halal').setInputFiles({name:oldName,mimeType:'application/pdf',buffer:bytes});
 const[uploaded]=await Promise.all([p.waitForResponse(r=>r.url().endsWith('/dossiers/'+dossier+'/documents')&&r.request().method()==='POST'),p.getByRole('button',{name:'Đính kèm tài liệu',exact:true}).click()]);
 expect(uploaded.status(),await uploaded.text()).toBe(200);const oldId=(await uploaded.json()).document_id;
 await expect(p.getByRole('status').filter({hasText:'Tài liệu đã được đính kèm vào hồ sơ'})).toBeVisible();
 await p.getByTestId('dossier-submit-cta').focus();await p.keyboard.press('Enter');await p.waitForURL('**/submissions?dossier_id='+dossier);
 await p.getByRole('button',{name:'Gửi hồ sơ mới',exact:true}).click();
 await p.getByRole('dialog',{name:'Gửi hồ sơ đến tổ chức chứng nhận',exact:true}).getByRole('button').filter({hasText:config.actors.cbX.email.split('@')[0]}).click();
 const dialog=p.getByRole('dialog',{name:'Gửi hồ sơ đến tổ chức chứng nhận',exact:true});
 await dialog.locator('button').first().focus();const focusable=await dialog.locator('button,input,textarea,select,a[href]').count();for(let i=0;i<focusable+2;i++){await p.keyboard.press('Tab');expect(await dialog.evaluate(el=>el.contains(document.activeElement))).toBe(true);}
 for(const box of await p.getByRole('checkbox').all())await box.uncheck();
 await p.locator('label').filter({hasText:oldName}).getByRole('checkbox').check();
 const receipts:any[]=[],requests:any[]=[];
 await p.route('**/api/api/submissions/submit',async route=>{
  requests.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});
  const r=await route.fetch();expect(r.status()).toBe(200);receipts.push(await r.json());
  if(requests.length===1)await route.abort('failed');else await route.fulfill({response:r});
 });
 await p.getByRole('button',{name:'Gửi 1 tài liệu',exact:true}).click();await expect(p.getByRole('alert').filter({hasText:'Giữ nguyên nội dung và thử lại'})).toBeVisible();
 await p.getByRole('button',{name:'Gửi 1 tài liệu',exact:true}).click();await expect(p.getByRole('dialog',{name:'Gửi hồ sơ đến tổ chức chứng nhận',exact:true})).toHaveCount(0);await p.unroute('**/api/api/submissions/submit');
 expect(requests).toHaveLength(2);expect(requests[0].key).toBeTruthy();expect(requests[0]).toEqual(requests[1]);expect(receipts[1].submission_id).toBe(receipts[0].submission_id);
 expect(requests[0].body.dossier_id).toBe(dossier);expect(requests[0].body.document_ids).toEqual([oldId]);const sub=receipts[0].submission_id;
 expect(requests[0].body.provider_id).toBe(config.actors.cbX.id);
 const sentCard=p.locator('[data-submission-id="'+sub+'"]');
 await expect(sentCard.getByText('Tổ chức tiếp nhận',{exact:true})).toBeVisible();
 await expect(sentCard.getByText(config.actors.cbX.email.split('@')[0],{exact:true})).toBeVisible();
 await expect(sentCard.getByText('Email liên hệ: '+config.actors.cbX.email,{exact:true})).toBeVisible();
 fs.writeFileSync(config.output+'/recovery-fixture.json',JSON.stringify({dossier,title:fixture.name,submission:sub,document:oldId,sha256:crypto.createHash('sha256').update(bytes).digest('hex')}));
 await login(q,'cbX');await expand(q,'cbX',sub);
 const[review]=await Promise.all([q.waitForResponse(r=>r.url().endsWith('/'+sub+'/status')&&r.request().method()==='PUT'),q.getByRole('button',{name:'Đang đánh giá',exact:true}).click()]);expect(review.status()).toBe(200);
 const form=q.locator('[data-form="request-revision"]');await form.locator('textarea').fill(fixture.name+' correction');
 const cbRequests:any[]=[],cbReceipts:any[]=[];
 await q.route('**/request-revision',async route=>{cbRequests.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();expect(response.status()).toBe(200);cbReceipts.push(await response.json());if(cbRequests.length===1)await route.abort('failed');else await route.fulfill({response});});
 await form.getByRole('button',{name:'Gửi yêu cầu sửa cho doanh nghiệp',exact:true}).click();await expect(form.getByRole('alert')).toBeVisible();
 await form.getByRole('button',{name:'Gửi yêu cầu sửa cho doanh nghiệp',exact:true}).click();await expect.poll(()=>cbReceipts.length).toBe(2);expect(cbRequests[0].key).toBeTruthy();expect(cbRequests[0]).toEqual(cbRequests[1]);expect(cbReceipts[0]).toEqual(cbReceipts[1]);await q.unroute('**/request-revision');
 await expand(p,'bizA',sub);await expect(p.locator('[data-revision-panel]')).toContainText(fixture.name+' correction');
 const[chooser]=await Promise.all([p.waitForEvent('filechooser'),p.getByTitle('Thay bằng phiên bản mới',{exact:true}).click()]);
 const replacement=p.waitForResponse(r=>r.url().endsWith('/replace-document')&&r.request().method()==='PUT');await chooser.setFiles({name:newName,mimeType:'application/pdf',buffer:pdf(fixture.name+' replacement')});const replaced=await replacement;expect(replaced.status()).toBe(200);const newId=replaced.request().postDataJSON().new_doc_id;
 await expect(p.getByRole('region',{name:'So sánh bằng chứng vòng 1'})).toContainText(oldName+' → '+newName);
 const resubmit=p.locator('[data-form="resubmit"]');await resubmit.locator('textarea').fill(fixture.name+' response');
 const resubmitRequests:any[]=[],resubmitReceipts:any[]=[];
 await p.route('**/resubmit',async route=>{resubmitRequests.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();expect(response.status()).toBe(200);resubmitReceipts.push(await response.json());if(resubmitRequests.length===1)await route.abort('failed');else await route.fulfill({response});});
 await resubmit.getByRole('button',{name:'Đã sửa — gửi lại cho CB',exact:true}).click();await expect(resubmit.getByRole('alert')).toBeVisible();
 await resubmit.getByRole('button',{name:'Đã sửa — gửi lại cho CB',exact:true}).click();await expect.poll(()=>resubmitReceipts.length).toBe(2);expect(resubmitRequests[0].key).toBeTruthy();expect(resubmitRequests[0]).toEqual(resubmitRequests[1]);expect(resubmitRequests[0].body.new_document_ids).toBeUndefined();expect(resubmitReceipts[0]).toEqual(resubmitReceipts[1]);await p.unroute('**/resubmit');
 await expand(q,'cbX',sub);await expect(q.locator('[data-revision-panel]')).toContainText(fixture.name+' response');await expect(q.getByRole('region',{name:'So sánh bằng chứng vòng 1'})).toContainText(oldName+' → '+newName);expect(errors).toEqual([]);
 const qToken=await token(request,'cbX');const historical=await request.get(config.base_url+'/api/api/documents/'+oldId+'/file',{headers:{Authorization:'Bearer '+qToken}});expect(historical.status()).toBe(200);expect(crypto.createHash('sha256').update(await historical.body()).digest('hex')).toBe(crypto.createHash('sha256').update(bytes).digest('hex'));
 fs.writeFileSync(config.output+'/recovery-fixture.json',JSON.stringify({dossier,title:fixture.name,submission:sub,document:oldId,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),files:[{id:oldId,sha256:crypto.createHash('sha256').update(bytes).digest('hex')},{id:newId,sha256:crypto.createHash('sha256').update(pdf(fixture.name+' replacement')).digest('hex')}],receipts:{submit:{key:requests[0].key,body:requests[0].body,response:receipts[0]},correction:{key:cbRequests[0].key,body:cbRequests[0].body,response:cbReceipts[0]},resubmit:{key:resubmitRequests[0].key,body:resubmitRequests[0].body,response:resubmitReceipts[0]}}}));
 await p.setViewportSize({width:390,height:844});expect(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await info.attach('mobile-correction',{body:await p.screenshot({fullPage:true}),contentType:'image/png'});

 const round2=q.locator('[data-form="request-revision"]');await round2.locator('textarea').fill(fixture.name+' correction round two');
 const[secondRequest]=await Promise.all([q.waitForResponse(r=>r.url().endsWith('/request-revision')&&r.request().method()==='POST'),round2.getByRole('button',{name:'Gửi yêu cầu sửa cho doanh nghiệp',exact:true}).click()]);expect(secondRequest.status()).toBe(200);
 await expand(p,'bizA',sub);await expect(p.locator('[data-revision-panel]')).toContainText(fixture.name+' correction');await expect(p.locator('[data-revision-panel]')).toContainText(fixture.name+' correction round two');
 const secondForm=p.locator('[data-form="resubmit"]');await secondForm.locator('textarea').fill(fixture.name+' response round two');const[secondSent]=await Promise.all([p.waitForResponse(r=>r.url().endsWith('/resubmit')&&r.request().method()==='POST'),secondForm.getByRole('button',{name:'Đã sửa — gửi lại cho CB',exact:true}).click()]);expect(secondSent.status()).toBe(200);
 await expand(q,'cbX',sub);await expect(q.locator('[data-revision-panel]')).toContainText(fixture.name+' response round two');await expect(q.locator('[data-revision-panel]')).toContainText(fixture.name+' response');await expect(q.getByRole('region',{name:'So sánh bằng chứng vòng 2'})).toContainText(newName);
 const rounds=await api(request,qToken,'/api/submissions/'+sub+'/revisions');const history=rounds.revisions||rounds.history||rounds;expect(Array.isArray(history)).toBe(true);expect(history.find((r:any)=>r.round===1).submitted_document_ids).toEqual([oldId]);expect(history.find((r:any)=>r.round===2).submitted_document_ids).toEqual([newId]);
 await info.attach('retained-correction',{body:await q.screenshot({fullPage:true}),contentType:'image/png'});
 await info.attach('business-evidence',{body:JSON.stringify({dossier,submission:sub,old_document:oldId,new_document:newId,submission_replayed:true}),contentType:'application/json'});
 }finally{await context.close();await cbContext.close();}
});

test('AUTH-01 @AUTH-02 @AUTH-06 business, member and CB login forms preserve role and identity',async({browser},info)=>{
 for(const actor of ['bizA','member','cbX'] as const){
  const ctx=await browser.newContext();try{const p=await ctx.newPage();await login(p,actor);await expect(p.locator('body')).toContainText(config.actors[actor].email.split('@')[0]);await info.attach('login-'+actor,{body:await p.screenshot(),contentType:'image/png'});}finally{await ctx.close();}
 }
});

test('AUTH-02 @AUTH-02 wrong password must not create authenticated session',async({page})=>{
 await page.goto('/business/login');await page.locator('input[type=email]').fill(config.actors.bizA.email);await page.locator('input[type=password]').fill('DeliberatelyWrong-Only-UAT-123!');
 const[r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/auth/login')),page.getByRole('button',{name:'Đăng nhập',exact:true}).click()]);expect(r.status()).toBe(401);await expect(page).toHaveURL(/\/business\/login/);
});

test('NAV-01 @ORG-04 @DOS-01 @CB-05 owner dossier navigation and provider redirect',async({browser},info)=>{
 for(const actor of ['bizA','cbX'] as const){const ctx=await browser.newContext();try{const p=await ctx.newPage();await login(p,actor);
  if(actor==='bizA'){await expect(p.getByRole('link',{name:'Hồ sơ chứng nhận',exact:true})).toBeVisible();await p.getByRole('link',{name:'Hồ sơ chứng nhận',exact:true}).click();await p.waitForURL('**/dossiers');}
  else{await p.goto('/dossiers');await p.waitForURL('**/submissions');}
  await info.attach('navigation-'+actor,{body:await p.screenshot(),contentType:'image/png'});
 }finally{await ctx.close();}}
});

test('[API] PERM-01 @ORG-04 @DOC-05 @E2E-12 read-only member cannot promote or invoke AI persistence',async({page,request})=>{
 const owner=await login(page,'bizA');const uploaded=await request.post(config.base_url+'/api/api/documents/upload',{headers:{Authorization:'Bearer '+owner},multipart:{doc_type:'halal_policy',file:{name:config.run_id+'-permission.pdf',mimeType:'application/pdf',buffer:pdf('Permission UAT')}}});expect(uploaded.status()).toBe(200);const doc=(await uploaded.json()).id;
 const member=await token(request,'member');for(const[path,body]of [['/api/documents/'+doc+'/promote',{}]] as const){const r=await request.post(config.base_url+'/api'+path,{headers:{Authorization:'Bearer '+member},data:body});expect(r.status()).toBe(403);}
 const ai=await request.post(config.base_url+'/api/evaluate',{headers:{Authorization:'Bearer '+member},multipart:{file:{name:'denied.pdf',mimeType:'application/pdf',buffer:pdf('No LLM call allowed')}}});expect(ai.status()).toBe(403);
});
