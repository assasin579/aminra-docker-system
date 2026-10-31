import { test, expect } from '@playwright/test';
import { api, config, packet, token } from './helpers';
test.use({serviceWorkers:'allow'});
test('SERVICE-WORKER-ISOLATION @AUTH-04 @DAT-01 old audit cache is evicted and offline user B never receives user A response',async({page,context,request})=>{
 await packet(request,'sw-scope');const a=await token(request,'cbX'),b=await token(request,'cbY');
 const visit=await api(request,a,'/api/audits/','POST',{business_tenant:config.actors.bizA.id,visit_type:'initial',scheduled_date:'2026-11-02',notes:'Synthetic private A audit'});
 const path='/api/api/audits/'+visit.id;
 await page.goto('/offline.html');
 await page.evaluate(async url=>{const cache=await caches.open('aminra-v9');await cache.put(url,new Response(JSON.stringify({secret:'synthetic old tenant A'}),{headers:{'Content-Type':'application/json'}}));await navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'});await navigator.serviceWorker.ready;},path);
 await page.reload();await page.waitForFunction(()=>!!navigator.serviceWorker.controller);
 expect(await page.evaluate(()=>caches.keys())).not.toContain('aminra-v9');
 const first=await page.evaluate(async({url,t})=>{const r=await fetch(url,{headers:{Authorization:'Bearer '+t}});return {status:r.status,body:await r.text()};},{url:path,t:a});expect(first.status).toBe(200);expect(first.body).toContain('Synthetic private A audit');
 await context.setOffline(true);
 const second=await page.evaluate(async({url,t})=>{try{const r=await fetch(url,{headers:{Authorization:'Bearer '+t}});return {offline:false,body:await r.text()};}catch{return {offline:true,body:''};}},{url:path,t:b});
 expect(second.offline).toBe(true);expect(second.body).toBe('');
 await context.setOffline(false);
 const cached=await page.evaluate(async()=>{const urls:string[]=[];for(const name of await caches.keys())for(const r of await(await caches.open(name)).keys())urls.push(r.url);return urls;});expect(cached.some(url=>url.includes('/api/'))).toBe(false);
});
