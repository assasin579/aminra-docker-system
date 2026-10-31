import {test,expect} from '@playwright/test';
import {randomUUID} from 'node:crypto';
import {api,config,login,pdf,prepare,token} from './helpers';

test('[API] SCOPE-01 @CB-05 @DOC-05 @DOC-07 @E2E-12 CB sees exact packet, not another dossier or another tenant',async({request},info)=>{
 const f=await prepare(request,'scope'),cb=await token(request,'cbX'),foreign=await token(request,'cbY');
 const dossiers=[];for(const name of ['sent','private'])dossiers.push(await api(request,f.biz,'/dossiers','POST',{title:f.name+' '+name,standard_type_id:f.standard.id}));
 const docs=[];for(let i=0;i<2;i++){
  const r=await request.post(config.base_url+'/api/dossiers/'+dossiers[i].id+'/documents',{headers:{Authorization:'Bearer '+f.biz,'Idempotency-Key':randomUUID()},multipart:{doc_type:'halal_policy',file:{name:f.name+'-'+i+'.pdf',mimeType:'application/pdf',buffer:pdf('Scope '+i)}}});expect(r.status(),await r.text()).toBe(200);docs.push((await r.json()).document_id);
 }
 const sub=await api(request,f.biz,'/api/submissions/submit','POST',{provider_id:config.actors.cbX.id,document_ids:[docs[0]],dossier_id:dossiers[0].id});
 const history=await api(request,cb,'/api/submissions/received/'+sub.submission_id+'/doc-revisions/halal_policy');expect(history.revisions.map((r:any)=>r.id)).toEqual([docs[0]]);
 const wrong=await request.get(config.base_url+'/api/api/submissions/received/'+sub.submission_id+'/doc-revisions/halal_policy',{headers:{Authorization:'Bearer '+foreign}});expect(wrong.status()).toBe(404);
 const other=await token(request,'bizB');const denied=await request.get(config.base_url+'/api/api/documents/'+docs[0]+'/file',{headers:{Authorization:'Bearer '+other}});expect(denied.status()).toBe(404);
 await info.attach('packet-exclusion',{body:JSON.stringify({submission:sub.submission_id,visible:docs[0],excluded:docs[1],foreign_cb_status:wrong.status()}),contentType:'application/json'});
});

test('[API] VERSION-01 @DOC-05 @DOC-06 owner current selection is idempotent and preserves chronology and approval',async({request})=>{
 const owner=await token(request,'bizA');const r=await request.post(config.base_url+'/api/api/documents/upload',{headers:{Authorization:'Bearer '+owner},multipart:{doc_type:'halal_policy',file:{name:config.run_id+'-version.pdf',mimeType:'application/pdf',buffer:pdf('Version UAT')}}});expect(r.status()).toBe(200);const doc=(await r.json()).id;
 const before=await api(request,owner,'/api/documents/'+doc);const first=await api(request,owner,'/api/documents/'+doc+'/promote','POST');expect(first.changed).toBe(true);
 const again=await api(request,owner,'/api/documents/'+doc+'/promote','POST');expect(again.changed).toBe(false);
 const after=await api(request,owner,'/api/documents/'+doc);expect(after.uploaded_at).toBe(before.uploaded_at);expect(after.approval_status).toBe(before.approval_status);expect(after.is_current_selection).toBe(true);
});

test('MEMBER-01 @ORG-04 @SUB-01 member sees dossier without owner-only actions',async({page,request})=>{
 const f=await prepare(request,'readonly');const d=await api(request,f.biz,'/dossiers','POST',{title:f.name,standard_type_id:f.standard.id});await login(page,'member');await page.goto('/dossiers/'+d.id);
 await expect(page.getByRole('button',{name:'Đính kèm tài liệu',exact:true})).toHaveCount(0);await expect(page.getByTestId('dossier-submit-cta')).toHaveCount(0);await expect(page.getByTestId('dossier-create-doc-cta')).toHaveCount(0);
 const ownerCalls:string[]=[];page.on('request',r=>{if(r.url().includes('/my-submissions'))ownerCalls.push(r.url());});await page.goto('/submissions');await page.waitForURL('**/dossiers');expect(ownerCalls).toEqual([]);
});

test('CLOSED-01 @SUB-07 cancelled dossier remains readable and hides mutations',async({page,request})=>{
 const f=await prepare(request,'cancelled');const d=await api(request,f.biz,'/dossiers','POST',{title:f.name,standard_type_id:f.standard.id});await api(request,f.biz,'/dossiers/'+d.id,'PATCH',{status:'cancelled'});
 await login(page,'bizA');await page.goto('/dossiers/'+d.id);await expect(page.getByText('Hồ sơ đã hủy. Chỉ hiển thị thông tin và tài liệu đã lưu.',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Đính kèm tài liệu',exact:true})).toHaveCount(0);await expect(page.getByTestId('certification-readiness-panel')).toHaveCount(0);
});

test('PINNED-01 @STD-03 @STD-04 @DOS-06 @E2E-05 published v2 does not change old dossier requirements',async({page,request},info)=>{
 const f=await prepare(request,'pinned');const old=await api(request,f.biz,'/dossiers','POST',{title:f.name+' old',standard_type_id:f.standard.id});const before=await api(request,f.biz,'/dossiers/'+old.id+'/readiness');
 await api(request,f.admin,'/auth/admin/standard-types/'+f.standard.id+'/doc-types','PUT',{doc_types:[{doc_type:'halal_policy',required:true,display_order:0},{doc_type:'has_manual',required:true,display_order:1}]});await api(request,f.admin,'/auth/admin/standard-types/'+f.standard.id+'/publish-requirements','POST');
 const newer=await api(request,f.biz,'/dossiers','POST',{title:f.name+' new',standard_type_id:f.standard.id});const after=await api(request,f.biz,'/dossiers/'+old.id+'/readiness');const fresh=await api(request,f.biz,'/dossiers/'+newer.id+'/readiness');expect(after.requirements_version_id).toBe(before.requirements_version_id);expect(fresh.requirements_version_id).not.toBe(before.requirements_version_id);
 await login(page,'bizA');await page.goto('/dossiers/'+old.id);await expect(page.getByLabel('Tệp mới cho Chính sách Halal')).toBeVisible();await expect(page.getByLabel('Tệp mới cho Sổ tay HAS')).toHaveCount(0);
 await info.attach('pinned-requirements',{body:JSON.stringify({old:after,new:fresh}),contentType:'application/json'});
});

test('LIBRARY-01 @DOC-05 @DOS-06 library renders two independent same-type uploads',async({page,request})=>{
 const owner=await login(page,'bizB');const names=[config.run_id+'-one.pdf',config.run_id+'-two.pdf'];for(const name of names){const r=await request.post(config.base_url+'/api/api/documents/upload',{headers:{Authorization:'Bearer '+owner},multipart:{doc_type:'halal_policy',file:{name,mimeType:'application/pdf',buffer:pdf(name)}}});expect(r.status()).toBe(200);}
 await page.goto('/documents');for(const name of names)await expect(page.getByText(name,{exact:true})).toBeVisible();
});

test('SESSION-01 @AUTH-04 @E2E-12 logout and account switch do not render previous business files',async({page,request})=>{
 const owner=await login(page,'bizA');const sentinel=config.run_id+'-private-switch.pdf';
 const r=await request.post(config.base_url+'/api/api/documents/upload',{headers:{Authorization:'Bearer '+owner},multipart:{doc_type:'halal_policy',file:{name:sentinel,mimeType:'application/pdf',buffer:pdf(sentinel)}}});expect(r.status()).toBe(200);
 await page.goto('/documents');await expect(page.getByText(sentinel,{exact:true})).toBeVisible();
 await page.getByRole('button').filter({hasText:config.actors.bizA.email}).first().click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
 await login(page,'bizB');await page.goto('/documents');await expect(page.getByRole('heading',{name:'Kho tài liệu',exact:true})).toBeVisible();await expect(page.getByText(sentinel,{exact:true})).toHaveCount(0);
});
