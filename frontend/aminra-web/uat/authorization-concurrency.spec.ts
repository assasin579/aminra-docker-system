import { test, expect } from '@playwright/test';
import { api, config, token, packet, login, control, type Actor } from './helpers';

test('[API] AUTHORIZATION-CONTAMINATION @AUTH-04 @AUTH-06 @ORG-04 @CB-03 @CB-05 @DAT-01 @E2E-12 interleaved concurrent users keep identity, data and write authority isolated',async({request},info)=>{
 const f=await packet(request,'principal-isolation');
 const actors:Actor[]=['bizA','bizB','cbX','cbY','member','assigned','unassigned','admin'];
 const tokens=Object.fromEntries(await Promise.all(actors.map(async actor=>[actor,await token(request,actor)])));
 await api(request,tokens.cbX,`/api/submissions/received/${f.submission}/assign`,'PUT',{auditor_id:config.actors.assigned.id});
 const visit=await api(request,tokens.cbX,'/api/audits/','POST',{business_tenant:config.actors.bizA.id,visit_type:'initial',scheduled_date:'2026-11-02'});
 await api(request,tokens.cbX,`/api/audits/${visit.id}/assign`,'PUT',{auditor_id:config.actors.assigned.id});
 const item=await api(request,tokens.cbX,`/api/audits/${visit.id}/items`,'POST',{criteria:'Isolation sentinel',severity:'minor'});
 const results:{actor:Actor;operation:string;actual:number;expected:number}[]=[];
 const operations=Array.from({length:5},(_,round)=>actors.map((actor,index)=>({actor:actors[(index+round)%actors.length],round}))).flat();
 async function check(actor:Actor,round:number){
  const headers={Authorization:'Bearer '+tokens[actor]};
  const me=await request.get(config.base_url+'/api/auth/me',{headers});
  expect(me.status(),await me.text()).toBe(200);const profile=await me.json();
  expect(profile.id).toBe(config.actors[actor].id);expect(profile.email).toBe(config.actors[actor].email);expect(profile.tenant_id).toBe(config.actors[actor].tenant_id);expect(profile.is_owner).toBe(config.actors[actor].is_owner);
  const file=await request.get(config.base_url+`/api/api/documents/${f.document}/file`,{headers});
  results.push({actor,operation:'shared-file',actual:file.status(),expected:['bizA','member','cbX','assigned'].includes(actor)?200:404});
  const roleDenied=['bizA','bizB','member','admin'].includes(actor);
  const permitted=['cbX','assigned'].includes(actor);
  const update=await request.put(config.base_url+`/api/api/audits/${visit.id}/items/${item.id}`,{headers,data:{note:config.run_id+':'+actor+':'+round}});
  results.push({actor,operation:'audit-write',actual:update.status(),expected:permitted?200:roleDenied?403:404});
  const promote=await request.post(config.base_url+`/api/api/documents/${f.document}/promote`,{headers});
  results.push({actor,operation:'current-selection',actual:promote.status(),expected:actor==='bizA'?200:actor==='bizB'?404:403});
 }
 // Twenty outstanding principals share one HTTP request context/connection pool.
 for(let offset=0;offset<operations.length;offset+=20)await Promise.all(operations.slice(offset,offset+20).map(({actor,round})=>check(actor,round)));
 await info.attach('concurrent-principal-matrix',{body:JSON.stringify(results,null,2),contentType:'application/json'});
 expect(results.filter(r=>r.actual!==r.expected)).toEqual([]);
 const final=await api(request,tokens.cbX,`/api/audits/${visit.id}`);
 expect(final.items).toHaveLength(1);expect(final.items[0].note).toMatch(new RegExp('^'+config.run_id+':(cbX|assigned):'));
 const proof=control('authorization_state',{document:f.document,visit:visit.id});
 expect(proof.selected_by).toBe(config.actors.bizA.id);expect(proof.document_tenant).toBe(config.actors.bizA.id);expect(proof.provider_id).toBe(config.actors.cbX.id);
 await info.attach('persisted-principal-evidence',{body:JSON.stringify(proof,null,2),contentType:'application/json'});
});

test('MULTITAB-IDENTITY @AUTH-04 @AUTH-06 @RPT-06 @E2E-12 an existing tab stops using the previous account after another tab signs in',async({page,context,request})=>{
 const f=await packet(request,'multi-tab');
 await login(page,'bizA');await page.goto('/documents');
 await expect(page.getByText(f.name,{exact:true})).toBeVisible();
 const other=await context.newPage();await other.goto('/documents');
 // Existing sessions correctly redirect away from /login. Complete the real
 // password exchange, then publish its session as the login/SSO callback does.
 const nextToken=await token(request,'bizB');
 const nextMe=await request.get(config.base_url+'/api/auth/me',{headers:{Authorization:'Bearer '+nextToken}});
 expect(nextMe.status()).toBe(200);const nextProfile=await nextMe.json();
 await other.evaluate(({accessToken,profile})=>{
  localStorage.setItem('aminra_user_token',accessToken);
  localStorage.setItem('aminra_user_profile',JSON.stringify(profile));
  window.dispatchEvent(new Event('aminra:auth-session-changed'));
 },{accessToken:nextToken,profile:nextProfile});
 await expect(other.getByText(f.name,{exact:true})).toHaveCount(0);
 await expect(page.getByText(f.name,{exact:true})).toHaveCount(0);
 const seen:string[]=[];
 page.on('request',req=>{if(req.url().includes('/api/'))seen.push(req.headers()['authorization'] || '');});
 await page.goto('/documents');
 await expect(page.getByText(f.name,{exact:true})).toHaveCount(0);
 const identity=await page.evaluate(async()=>{
  const t=localStorage.getItem('aminra_user_token');const response=await fetch('/api/auth/me',{headers:{Authorization:'Bearer '+t}});return response.json();
 });
 expect(identity.id).toBe(config.actors.bizB.id);expect(seen.some(value=>value.length>0)).toBe(true);
 await other.close();
});
