import { test, expect } from '@playwright/test';
import { api, config, token, packet, pdf } from './helpers';

test('[API] AUDIT-SCOPE @CB-03 @CB-05 @AUD-03 @AUD-06 @E2E-12 audit children deny foreign CB and unassigned staff before reads or writes', async ({ request }, info) => {
 const shared=await packet(request,'audit-scope');
 const owner=await token(request,'cbX'), foreign=await token(request,'cbY'), unassigned=await token(request,'unassigned');
 const visit=await api(request,owner,'/api/audits/','POST',{business_tenant:config.actors.bizA.id,visit_type:'initial',scheduled_date:'2026-11-02',location:config.run_id});
 const item=await api(request,owner,`/api/audits/${visit.id}/items`,'POST',{criteria:'Synthetic original criterion',severity:'minor'});
 const ncr=await api(request,owner,`/api/audits/${visit.id}/ncr`,'POST',{description:'Synthetic original finding',severity:'minor'});
 const attempts:[string,string,unknown?][]=[
  ['GET',`/api/audits/${visit.id}/items`],
  ['GET',`/api/audits/${visit.id}/ncr`],
  ['POST',`/api/audits/${visit.id}/items`,{criteria:'Foreign criterion',severity:'minor'}],
  ['PUT',`/api/audits/${visit.id}/items/${item.id}`,{note:'Unauthorized write'}],
  ['POST',`/api/audits/${visit.id}/ncr`,{description:'Foreign finding',severity:'minor'}],
  ['PUT',`/api/audits/${visit.id}/ncr/${ncr.id}`,{corrective_action:'Unauthorized write'}],
  ['PUT',`/api/audits/ncr/${ncr.id}/verify`,{action:'close'}],
  ['PUT',`/api/audits/${visit.id}/gps`,{type:'start',lat:10.7,lng:106.6}],
  ['POST',`/api/audits/${visit.id}/follow-up`,{scheduled_date:'2026-11-03'}],
  ['DELETE',`/api/audits/${visit.id}/items/${item.id}`],
 ];
 const unrelated=await request.post(config.base_url+'/api/api/audits/',{headers:{Authorization:'Bearer '+foreign},data:{business_tenant:config.actors.bizA.id,visit_type:'initial',scheduled_date:'2026-11-02'}});
 expect(unrelated.status()).toBe(404);
 const privateUpload=await request.post(config.base_url+'/api/api/documents/upload',{headers:{Authorization:'Bearer '+shared.biz},multipart:{doc_type:'halal_policy',file:{name:config.run_id+'-private-audit.pdf',mimeType:'application/pdf',buffer:pdf('Private evidence')}}});
 expect(privateUpload.status()).toBe(200);const privateId=(await privateUpload.json()).id;
 const portfolio=await api(request,owner,`/api/audits/businesses/${config.actors.bizA.id}/dossier`);
 expect(JSON.stringify(portfolio)).toContain(shared.document);expect(JSON.stringify(portfolio)).not.toContain(privateId);
 const foreignPortfolio=await request.get(config.base_url+`/api/api/audits/businesses/${config.actors.bizA.id}/dossier`,{headers:{Authorization:'Bearer '+foreign}});expect(foreignPortfolio.status()).toBe(404);
 const results=[];
 for(const [actor,t] of [['foreign',foreign],['unassigned',unassigned]]) {
  for(const [method,path,data] of attempts) {
   const response=await request.fetch(config.base_url+'/api'+path,{method,headers:{Authorization:'Bearer '+t},data});
   results.push({actor,method,path,status:response.status(),expected:actor==='unassigned'&&path.endsWith('/follow-up')?403:404});
  }
 }
 await info.attach('audit-scope-matrix',{body:JSON.stringify({visit:visit.id,results},null,2),contentType:'application/json'});
 expect(results.filter(row=>row.status!==row.expected)).toEqual([]);
 const detail=await api(request,owner,`/api/audits/${visit.id}`);
 expect(detail.items).toHaveLength(1);expect(detail.items[0].note).toBeFalsy();
 expect(detail.ncrs).toHaveLength(1);expect(detail.ncrs[0].status).toBe('open');
});


test('[API] AUDIT-IMMUTABILITY @AUD-04 @AUD-05 @AUD-06 @CB-06 accepted report freezes observations and preserves assigned-only report access',async({request},info)=>{
 const f=await packet(request,'frozen-audit');const owner=await token(request,'cbX'), auditor=await token(request,'assigned'), other=await token(request,'unassigned'), foreign=await token(request,'cbY');
 const visit=await api(request,owner,'/api/audits/','POST',{business_tenant:config.actors.bizA.id,visit_type:'initial',scheduled_date:'2026-11-03',location:config.run_id});
 await api(request,owner,`/api/audits/${visit.id}/assign`,'PUT',{auditor_id:config.actors.assigned.id});
 const item=await api(request,auditor,`/api/audits/${visit.id}/items`,'POST',{criteria:'Synthetic original observation',severity:'minor'});
 await api(request,auditor,`/api/audits/${visit.id}/items/${item.id}`,'PUT',{result:'conform',note:'Synthetic field evidence reviewed'});
 await api(request,auditor,`/api/audits/${visit.id}/status`,'PUT',{status:'completed'});
 const ownerSubmit=await request.post(config.base_url+`/api/api/audits/${visit.id}/generate-report`,{headers:{Authorization:'Bearer '+owner}});expect(ownerSubmit.status()).toBe(403);
 await api(request,auditor,`/api/audits/${visit.id}/generate-report`,'POST');
 const selfAccept=await request.post(config.base_url+`/api/api/audits/${visit.id}/accept-report`,{headers:{Authorization:'Bearer '+auditor}});expect(selfAccept.status()).toBe(403);
 await api(request,owner,`/api/audits/${visit.id}/accept-report`,'POST');
 const report=await request.get(config.base_url+`/api/api/audits/${visit.id}/report-pdf`,{headers:{Authorization:'Bearer '+auditor}});expect(report.status()).toBe(200);const bytes=await report.body();expect(bytes.subarray(0,4).toString()).toBe('%PDF');
 for(const t of [other,foreign]) {const denied=await request.get(config.base_url+`/api/api/audits/${visit.id}/report-pdf`,{headers:{Authorization:'Bearer '+t}});expect(denied.status()).toBe(404);}
 for(const [method,path,data] of [
  ['PUT',`/api/audits/${visit.id}/items/${item.id}`,{note:'Changed after acceptance'}],
  ['POST',`/api/audits/${visit.id}/items`,{criteria:'New observation'}],
  ['DELETE',`/api/audits/${visit.id}/items/${item.id}`,undefined],
  ['PUT',`/api/audits/${visit.id}/gps`,{type:'start',lat:10,lng:106}],
  ['PUT',`/api/audits/${visit.id}/status`,{status:'completed'}],
 ] as const) {const denied=await request.fetch(config.base_url+'/api'+path,{method,headers:{Authorization:'Bearer '+auditor},data});expect(denied.status(),await denied.text()).toBe(409);}
 const after=await request.get(config.base_url+`/api/api/audits/${visit.id}/report-pdf`,{headers:{Authorization:'Bearer '+owner}});expect(await after.body()).toEqual(bytes);
 await info.attach('accepted-report',{body:bytes,contentType:'application/pdf'});
 expect((await api(request,owner,`/api/audits/${visit.id}`)).visit.status).toBe('report_accepted');
});

test('[API] AUDIT-UPLOAD-SCOPE @CB-05 @DOC-04 @AUD-03 @E2E-12 uploads check parent assignment before filesystem writes',async({request},info)=>{
 await packet(request,'audit-upload');const owner=await token(request,'cbX');
 const visit=await api(request,owner,'/api/audits/','POST',{business_tenant:config.actors.bizA.id,visit_type:'initial',scheduled_date:'2026-11-02'});
 const item=await api(request,owner,`/api/audits/${visit.id}/items`,'POST',{criteria:'Photo ownership',severity:'minor'});
 const ncr=await api(request,owner,`/api/audits/${visit.id}/ncr`,'POST',{description:'Photo scope',severity:'minor'});
 const bytes=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII=','base64');
 const results=[];
 for(const actor of ['cbY','unassigned'] as const) {
  const t=await token(request,actor);
  for(const path of [`/api/audits/${visit.id}/items/${item.id}/photo`,`/api/audits/${visit.id}/ncr/${ncr.id}/photo`,`/api/audits/${visit.id}/signature`]) {
   const response=await request.post(config.base_url+'/api'+path,{headers:{Authorization:'Bearer '+t},multipart:{file:{name:'proof.png',mimeType:'image/png',buffer:bytes}}});
   results.push({actor,path,status:response.status()});expect(response.status(),await response.text()).toBe(404);
  }
 }
 const uploaded=await request.post(config.base_url+`/api/api/audits/${visit.id}/items/${item.id}/photo`,{headers:{Authorization:'Bearer '+owner},multipart:{file:{name:'../../scope-proof.png',mimeType:'image/png',buffer:bytes}}});
 expect(uploaded.status(),await uploaded.text()).toBe(200);expect((await uploaded.json()).path).not.toContain('..');
 await info.attach('upload-parent-matrix',{body:JSON.stringify(results,null,2),contentType:'application/json'});
});
