import {test, expect, type Page} from '@playwright/test';
import {config, login, token, api, control} from './helpers';

const complaintPath = '/api/api/complaints';
const conflictPath = '/api/api/conflicts';
async function post(page:Page, path:string, button:string, status=200) {
 const [response] = await Promise.all([
  page.waitForResponse(r => new URL(r.url()).pathname === path && r.request().method() === 'POST',{timeout:15000}),
  page.getByRole('button',{name:button,exact:true}).click(),
 ]);
 expect(response.status(), await response.text()).toBe(status);
 if(status===200) await expect(page.getByRole('status')).toContainText('Saved');
 return response.json();
}
async function complaintForm(page:Page, title:string) {
 await page.goto('/complaints');
 await page.getByRole('combobox',{name:'Certification provider',exact:true}).selectOption(config.actors.cbX.id);
 await page.getByLabel('Case type',{exact:true}).selectOption('complaint_service');
 await page.getByLabel('Title',{exact:true}).fill(title);
 await page.getByLabel('Description',{exact:true}).fill('Synthetic UAT service complaint: '+title);
}
async function declarationForm(page:Page, description:string) {
 await page.goto('/conflicts');
 await page.getByLabel('Business tenant',{exact:true}).fill(config.actors.bizA.id);
 await page.getByLabel('Person user ID',{exact:true}).fill(config.actors.cbX.id);
 await page.getByLabel('Role',{exact:true}).selectOption('decision_maker');
 await page.getByLabel('Conflict type',{exact:true}).selectOption('consultancy');
 await page.getByLabel('Description',{exact:true}).fill(description);
}

test('COMPLAINT-01 @CMP-01 @E2E-11 business intake, CB assignment and complete lifecycle persist after reload',async({page,request},info)=>{
 const bizToken=await login(page,'bizA');const title=config.run_id+' service complaint';
 await complaintForm(page,title);
 const saved=await post(page,complaintPath,'Submit case');expect(saved.status).toBe('received');
 expect(saved.provider_id).toBe(config.actors.cbX.id);expect(saved.business_tenant).toBe(config.actors.bizA.id);
 await page.reload();const row=page.getByTestId('case-'+saved.id);
 await expect(row).toContainText(title);await expect(row).toContainText('Status: received');
 await expect(page.getByRole('button',{name:'Assign',exact:true})).toHaveCount(0);
 const foreign=await token(request,'bizB');
 const denied=await request.get(config.base_url+complaintPath+'/'+saved.id,{headers:{Authorization:'Bearer '+foreign}});expect(denied.status()).toBe(404);
 await login(page,'cbX');await page.goto('/complaints');
 await page.getByLabel('Assignment case ID',{exact:true}).fill(saved.id);
 await page.getByLabel('Owner user ID',{exact:true}).fill(config.actors.cbX.id);
 await post(page,complaintPath+'/'+saved.id+'/assign','Assign');
 await expect(row).toContainText('Owner: '+config.actors.cbX.id);
 await page.getByLabel('Case ID',{exact:true}).fill(saved.id);
 await page.getByLabel('To status',{exact:true}).selectOption('closed');
 await page.getByLabel('Closure reason',{exact:true}).fill('Premature closure');
 await post(page,complaintPath+'/'+saved.id+'/transition','Update case status',409);
 await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText('Invalid status transition');
 await expect(row).toContainText('Status: received');
 for(const status of ['acknowledged','under_investigation','decision_made','closed']) {
  await page.getByLabel('To status',{exact:true}).selectOption(status);
  if(status==='decision_made')await page.getByLabel('Decision summary',{exact:true}).fill('Reviewed service records and corrective response.');
  if(status==='closed')await page.getByLabel('Closure reason',{exact:true}).fill('Corrective response delivered and recorded.');
  const changed=await post(page,complaintPath+'/'+saved.id+'/transition','Update case status');expect(changed.status).toBe(status);
  if(status!=='closed') expect(changed.closure_reason || '').toBe('');
  if(status==='closed') expect(changed.decision_summary).toBe('Reviewed service records and corrective response.');
 }
 await page.reload();await expect(row).toContainText('Status: closed');await expect(row).toContainText('Corrective response delivered');
 const own=await api(request,bizToken,'/api/complaints/'+saved.id);expect(own.status).toBe('closed');
 const evidence=control('trust_evidence',{entity:'complaint',id:saved.id});
 expect(evidence.events.map((e:{event_type:string})=>e.event_type)).toEqual(['case.created','case.assigned','case.transition','case.transition','case.transition','case.transition']);
 expect(evidence.events.filter((e:{event_type:string})=>e.event_type==='case.transition').map((e:{to_status:string})=>e.to_status)).toEqual(['acknowledged','under_investigation','decision_made','closed']);
 expect(evidence.audit.map((e:{action:string})=>e.action)).toEqual(['complaint.create','complaint.assign','complaint.transition','complaint.transition','complaint.transition','complaint.transition']);
 await info.attach('complaint-server-evidence',{body:JSON.stringify(evidence,null,2),contentType:'application/json'});
 await info.attach('complaint-closed',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
});

test('CONFLICT-01 @DEC-01 declaration, review and override persist and enforce assignment blocking',async({page,request},info)=>{
 const cb=await login(page,'cbX');const biz=await token(request,'bizA');
 const complaint=await api(request,biz,'/api/complaints','POST',{provider_id:config.actors.cbX.id,case_type:'complaint_service',source:'business',title:config.run_id+' conflict gate',description:'Synthetic independent handler check'});
 await declarationForm(page,config.run_id+' prior consultancy');
 const saved=await post(page,conflictPath,'Submit declaration');expect(saved.status).toBe('declared');
 await page.reload();const row=page.getByTestId('conflict-'+saved.id);await expect(row).toContainText('Status: declared');
 async function assignment(expected:number) {
  const r=await request.post(config.base_url+complaintPath+'/'+complaint.id+'/assign',{headers:{Authorization:'Bearer '+cb},data:{owner_id:config.actors.cbX.id}});
  expect(r.status(),await r.text()).toBe(expected);
  if(expected===409)expect((await r.json()).detail).toContain('Unresolved conflict');
 }
 await assignment(409);
 await page.getByLabel('Conflict ID',{exact:true}).fill(saved.id);
 for(const status of ['under_review','blocked','cleared']) {
  await page.getByLabel('Review status',{exact:true}).selectOption(status);
  await page.getByLabel('Review reason',{exact:true}).fill('Synthetic documented review: '+status);
  const changed=await post(page,conflictPath+'/'+saved.id+'/review','Save review');expect(changed.status).toBe(status);
  await assignment(status==='cleared'?200:409);
 }
 await page.getByLabel('Override conflict ID',{exact:true}).fill(saved.id);
 await page.getByLabel('Override reason',{exact:true}).fill('Unnecessary override attempt.');
 await post(page,conflictPath+'/'+saved.id+'/override','Override conflict',409);
 await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText('Cleared conflict does not require override');
 await expect(row).toContainText('Status: cleared');
 const staff=await token(request,'assigned');
 for(const suffix of ['/review','/override']) {
  const denied=await request.post(config.base_url+conflictPath+'/'+saved.id+suffix,{headers:{Authorization:'Bearer '+staff},data:suffix==='/review'?{status:'cleared',review_reason:'Staff attempt'}:{override_reason:'Staff attempt'}});
  expect(denied.status(),await denied.text()).toBe(403);
 }
 await page.getByLabel('Review status',{exact:true}).selectOption('blocked');
 await page.getByLabel('Review reason',{exact:true}).fill('Additional information requires block.');
 await post(page,conflictPath+'/'+saved.id+'/review','Save review');await assignment(409);
 await page.getByLabel('Override conflict ID',{exact:true}).fill(saved.id);
 await page.getByLabel('Override reason',{exact:true}).fill('Synthetic owner-authorized mitigation recorded.');
 const overridden=await post(page,conflictPath+'/'+saved.id+'/override','Override conflict');expect(overridden.status).toBe('overridden');await assignment(200);
 await page.reload();await expect(row).toContainText('Status: overridden');await expect(row).toContainText('owner-authorized mitigation');
 const foreign=await token(request,'cbY');
 for(const suffix of ['', '/review','/override']) {
  const r=await request.fetch(config.base_url+conflictPath+'/'+saved.id+suffix,{method:suffix?'POST':'GET',headers:{Authorization:'Bearer '+foreign},data:suffix==='/review'?{status:'cleared',review_reason:'Foreign attempt'}:suffix?{override_reason:'Foreign attempt'}:undefined});expect(r.status(),await r.text()).toBe(404);
 }
 const evidence=control('trust_evidence',{entity:'conflict',id:saved.id});
 expect(evidence.overrides).toEqual([{overridden_by:config.actors.cbX.id,override_reason:'Synthetic owner-authorized mitigation recorded.'}]);
 expect(evidence.audit.map((e:{action:string})=>e.action)).toEqual(['conflict.declare','conflict.review','conflict.review','conflict.review','conflict.review','conflict.override']);
 await info.attach('conflict-server-evidence',{body:JSON.stringify(evidence,null,2),contentType:'application/json'});
 await info.attach('conflict-overridden',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
});

test('COMPLAINT-VALIDATION @CMP-01 appeal requires decision; rejected reference preserves input without a receipt',async({page})=>{
 await login(page,'bizA');await complaintForm(page,config.run_id+' invalid appeal');
 await page.getByLabel('Case type',{exact:true}).selectOption('appeal_decision');
 const original=page.getByLabel('Original decision ID',{exact:true});await expect(original).toHaveAttribute('required','');
 await page.getByRole('button',{name:'Submit case',exact:true}).click();
 expect(await original.evaluate((el:HTMLInputElement)=>el.validity.valueMissing)).toBe(true);
 await original.fill('00000000-0000-4000-8000-000000000001');
 await post(page,complaintPath,'Submit case',404);
 await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText('Original certification decision not found');
 await expect(page.getByLabel('Title',{exact:true})).toHaveValue(config.run_id+' invalid appeal');
 await expect(page.getByRole('status')).toHaveCount(0);
 await page.reload();await expect(page.getByTestId('complaint-queue')).not.toContainText(config.run_id+' invalid appeal');
});

test('CONFLICT-VALIDATION @DEC-01 rejected declaration preserves fields and does not appear as saved',async({page})=>{
 await login(page,'cbX');await declarationForm(page,config.run_id+' invalid declaration');
 await page.getByLabel('Business tenant',{exact:true}).fill('invalid-business-id');
 await post(page,conflictPath,'Submit declaration',400);
 await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText('Invalid business_tenant');
 await expect(page.getByLabel('Description',{exact:true})).toHaveValue(config.run_id+' invalid declaration');
 await expect(page.getByRole('status')).toHaveCount(0);
 await page.reload();await expect(page.getByRole('region',{name:'Saved declarations'})).not.toContainText(config.run_id+' invalid declaration');
});

test('[API] TRUST-ROLE @CMP-01 @DEC-01 unrelated CB queues are empty and business cannot manage CB workflows',async({page,request})=>{
 const business=await login(page,'bizB');await page.goto('/conflicts');await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toHaveText('Provider access required.');await expect(page.getByRole('button',{name:'Submit declaration'})).toHaveCount(0);
 const conflict=await request.get(config.base_url+conflictPath,{headers:{Authorization:'Bearer '+business}});expect(conflict.status()).toBe(403);
 const other=await token(request,'cbY');
 const cases=await api(request,other,'/api/complaints');expect(cases.cases).toEqual([]);
 const conflicts=await api(request,other,'/api/conflicts');expect(conflicts.conflicts).toEqual([]);
 const forbidden=await request.post(config.base_url+complaintPath+'/00000000-0000-4000-8000-000000000001/transition',{headers:{Authorization:'Bearer '+business},data:{to_status:'acknowledged'}});expect(forbidden.status()).toBe(403);
});

async function responseLoss(page:Page, kind:'complaint'|'conflict') {
  await login(page,kind==='complaint'?'bizA':'cbX');
  const label=config.run_id+' response loss '+kind;
  if(kind==='complaint')await complaintForm(page,label);else await declarationForm(page,label);
  await expect(page.getByText('Loading register…',{exact:true})).toHaveCount(0);
  const path=kind==='complaint'?complaintPath:conflictPath;
  let writes=0;
  await page.route('**'+path,async route=>{
   if(route.request().method()!=='POST')return route.continue();
   writes++;const result=await route.fetch();expect(result.status(),await result.text()).toBe(200);
   await route.abort('connectionfailed');
  });
  await page.getByRole('button',{name:kind==='complaint'?'Submit case':'Submit declaration',exact:true}).click();
  await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText('reload the register before submitting again');
  await expect(page.getByRole('status')).toHaveCount(0);
  await expect(page.getByRole('button',{name:kind==='complaint'?'Submit case':'Submit declaration',exact:true})).toBeDisabled();
  await expect(page.getByLabel(kind==='complaint'?'Title':'Description',{exact:true})).toHaveValue(label);
  await page.unroute('**'+path);await page.reload();
  const queue=kind==='complaint'?page.getByTestId('complaint-queue'):page.getByRole('region',{name:'Saved declarations'});
  await expect(queue.locator('li').filter({hasText:label})).toHaveCount(1);expect(writes).toBe(1);

}

test('TRUST-RESPONSE-LOSS-COMPLAINT @CMP-01 lost write response recovers one persisted case after reload',async({page})=>{
 await responseLoss(page,'complaint');
});

test('TRUST-RESPONSE-LOSS-CONFLICT @DEC-01 lost write response recovers one persisted declaration after reload',async({page})=>{
 await responseLoss(page,'conflict');
});

test('TRUST-REFRESH-FAILURE @CMP-01 saved receipt survives a failed register refresh',async({page})=>{
 await login(page,'bizA');const label=config.run_id+' refresh failure';await complaintForm(page,label);
 await expect(page.getByText('Loading register…',{exact:true})).toHaveCount(0);
 await page.route('**'+complaintPath,route=>route.request().method()==='GET'?route.abort('connectionfailed'):route.continue());
 const saved=await post(page,complaintPath,'Submit case');
 await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText('Saved successfully, but the register could not refresh');
 await expect(page.getByTestId('case-'+saved.id)).toContainText(label);
 await expect(page.getByLabel('Title',{exact:true})).toHaveValue('');
 await page.unroute('**'+complaintPath);await page.reload();await expect(page.getByTestId('case-'+saved.id)).toContainText(label);
});

test('TRUST-MALFORMED-RECEIPT @CMP-01 a lost record identifier never claims success or repeats the persisted transaction',async({page})=>{
 await login(page,'bizA');const label=config.run_id+' unconfirmed receipt';await complaintForm(page,label);
 await expect(page.getByText('Loading register…',{exact:true})).toHaveCount(0);
 let writes=0;let savedId='';
 await page.route('**'+complaintPath,async route=>{
  if(route.request().method()!=='POST')return route.continue();
  writes++;const response=await route.fetch();expect(response.status()).toBe(200);savedId=(await response.json()).id;
  await route.fulfill({status:200,contentType:'application/json',body:'{}'});
 });
 await page.getByRole('button',{name:'Submit case',exact:true}).click();
 await expect(page.locator('[role="alert"]:not(#__next-route-announcer__)')).toContainText('did not confirm a saved record');
 await expect(page.getByRole('button',{name:'Submit case',exact:true})).toBeDisabled();
 await expect(page.getByRole('status')).toHaveCount(0);
 await expect(page.getByLabel('Title',{exact:true})).toHaveValue(label);
 await page.unroute('**'+complaintPath);await page.reload();
 await expect(page.getByTestId('case-'+savedId)).toContainText(label);
 await expect(page.getByTestId('complaint-queue').locator('li').filter({hasText:label})).toHaveCount(1);
 expect(writes).toBe(1);
});
