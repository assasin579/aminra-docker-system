import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {expect, type Page, type APIRequestContext} from '@playwright/test';
export const config=JSON.parse(fs.readFileSync(process.env.UAT_CONFIG!,'utf8'));
export type Actor='bizA'|'bizB'|'cbX'|'cbY'|'admin'|'member'|'assigned'|'unassigned';
export async function login(page:Page,actor:Actor){
 await page.route('**/*',route=>new URL(route.request().url()).origin===config.base_url?route.continue():route.abort('blockedbyclient'));
 const a=config.actors[actor];const kind=['cb_admin','auditor','platform_admin'].includes(a.role)?'provider':'business';
 await page.goto('/'+kind+'/login');
 await page.locator('input[type=email]').fill(a.email);await page.locator('input[type=password]').fill(a.password);
 const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/auth/login')&&r.request().method()==='POST'),page.getByRole('button',{name:'Đăng nhập',exact:true}).click()]);
 expect(r.status(),await r.text()).toBe(200);await page.waitForURL('**/dashboard/'+kind);
 return (await r.json()).access_token as string;
}
export async function token(api:APIRequestContext,actor:Actor){
 const a=config.actors[actor];const r=await api.post(config.base_url+'/api/auth/login',{data:{email:a.email,password:a.password,role:['cb_admin','auditor','platform_admin'].includes(a.role)?'provider':'business'}});
 expect(r.status(),await r.text()).toBe(200);return (await r.json()).access_token as string;
}
export async function api(api:APIRequestContext,t:string,path:string,method='GET',data?:unknown){
 const r=await api.fetch(config.base_url+'/api'+path,{method,headers:{Authorization:'Bearer '+t},data});
 expect(r.status(),await r.text()).toBeGreaterThanOrEqual(200);expect(r.status(),await r.text()).toBeLessThan(300);return r.json();
}
export async function prepare(apiContext:APIRequestContext,label:string,slots=[{doc_type:'halal_policy',required:true,display_order:0}],publish=true,business:'bizA'|'bizB'='bizA'){
 const admin=await token(apiContext,'admin'),biz=await token(apiContext,business);
 const name=config.run_id+'-'+label;
 const me=await api(apiContext,biz,'/auth/me');
 const industry=me.industry_schema_id?{id:me.industry_schema_id}:await api(apiContext,admin,'/auth/admin/industry-schemas','POST',{code:name.replace(/-/g,'_'),name_vi:name,enabled:true});
 if(!me.industry_schema_id)await api(apiContext,biz,'/industry-schemas/business-select','POST',{schema_id:industry.id});
 const standard=await api(apiContext,admin,'/auth/admin/standard-types','POST',{code:name.replace(/-/g,'_'),name_vi:name,organization:'Synthetic UAT',enabled:true});
 await api(apiContext,admin,'/auth/admin/standard-types/industries/'+industry.id+'/standards','PUT',{standards:[{standard_type_id:standard.id,is_default:true,display_order:0}]});
 await api(apiContext,admin,'/auth/admin/standard-types/'+standard.id+'/doc-types','PUT',{doc_types:slots});
 const version=publish?await api(apiContext,admin,'/auth/admin/standard-types/'+standard.id+'/publish-requirements','POST'):null;
 return {admin,biz,standard,version,name};
}
// Minimal valid PDF generated deterministically; no customer documents or LLM calls.
export function pdf(text:string){
 const content=`BT /F1 12 Tf 50 700 Td (${text.replace(/[()\\]/g,'_')}) Tj ET`;
 const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>','<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',`<< /Length ${Buffer.byteLength(content)} >>\nstream\n${content}\nendstream`];
 let out='%PDF-1.4\n',offsets=[0];for(let i=0;i<objects.length;i++){offsets.push(Buffer.byteLength(out));out+=`${i+1} 0 obj\n${objects[i]}\nendobj\n`;}
 const x=Buffer.byteLength(out);out+='xref\n0 6\n0000000000 65535 f \n'+offsets.slice(1).map(n=>String(n).padStart(10,'0')+' 00000 n \n').join('')+`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${x}\n%%EOF\n`;return Buffer.from(out);
}
export async function expand(page:Page,actor:'bizA'|'cbX',submission:string,business:'bizA'|'bizB'='bizA'){
 await page.goto('/submissions');const other=config.actors[actor==='bizA'?'cbX':business].email.split('@')[0];
 if(actor==='cbX')await page.getByRole('button').filter({hasText:other}).first().click();
 await Promise.all([page.waitForResponse(r=>r.url().includes('/submissions/'+submission+'/revisions')),page.getByRole('button').filter({hasText:other}).filter({hasNotText:'Quay lại'}).first().click()]);
}

export function control(kind:string,payload:unknown){
 return JSON.parse(execFileSync('python3',[path.resolve(__dirname,'../../../scripts/uat/control.py'),kind],{input:JSON.stringify(payload),encoding:'utf8',env:process.env}));
}
export async function makeDossier(request:APIRequestContext,f:any,label:string){
 return api(request,f.biz,'/dossiers','POST',{title:f.name+' '+label,standard_type_id:f.standard.id});
}
export async function attach(request:APIRequestContext,t:string,dossier:string,name:string,document?:string){
 const r=await request.post(config.base_url+'/api/dossiers/'+dossier+'/documents',{headers:{Authorization:'Bearer '+t,'Idempotency-Key':randomUUID()},multipart:document?{doc_type:'halal_policy',document_id:document}:{doc_type:'halal_policy',file:{name,mimeType:'application/pdf',buffer:pdf(name)}}});
 expect(r.status(),await r.text()).toBe(200);return (await r.json()).document_id as string;
}
export async function packet(request:APIRequestContext,label:string,business:'bizA'|'bizB'='bizA'){
 const f=await prepare(request,label,undefined,true,business),d=await makeDossier(request,f,'packet'),name=f.name+'.pdf';const document=await attach(request,f.biz,d.id,name);
 const result=await api(request,f.biz,'/api/submissions/submit','POST',{provider_id:config.actors.cbX.id,dossier_id:d.id,document_ids:[document]});
 return {...f,dossier:d.id,document,submission:result.submission_id,name};
}
