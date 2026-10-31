import fs from 'node:fs';
import crypto from 'node:crypto';
import {test,expect} from '@playwright/test';
import {config,control,login,token} from './helpers';
test('RECOVERY-01 @OPS-06 @E2E-14 login, dossier and exact file survive synthetic DB restore',async({page,request},info)=>{
 const fixture=JSON.parse(fs.readFileSync(config.output+'/recovery-fixture.json','utf8'));
 const t=await login(page,'bizA');await page.goto('/dossiers/'+fixture.dossier);await expect(page.getByRole('heading',{name:fixture.title,exact:true})).toBeVisible();
 const file=await request.get(config.base_url+'/api/api/documents/'+fixture.document+'/file',{headers:{Authorization:'Bearer '+t}});expect(file.status()).toBe(200);expect(crypto.createHash('sha256').update(await file.body()).digest('hex')).toBe(fixture.sha256);
 const cb=await token(request,'cbX');
 for(const original of fixture.files||[{id:fixture.document,sha256:fixture.sha256}]){
  const r=await request.get(config.base_url+'/api/api/documents/'+original.id+'/file',{headers:{Authorization:'Bearer '+cb}});expect(r.status()).toBe(200);const bytes=await r.body();expect(crypto.createHash('sha256').update(bytes).digest('hex')).toBe(original.sha256);
  const events=control('audit',{document:original.id});expect(events.some((e:any)=>e.action==='document.download_authorized')).toBe(true);expect(events.some((e:any)=>e.action==='document.download_response_started'&&e.metadata.response_status===200)).toBe(true);expect(events.some((e:any)=>e.action==='document.download_bytes_served'&&e.metadata.bytes_sent===bytes.length)).toBe(true);
 }
 if(fixture.receipts)for(const [name,receipt] of Object.entries(fixture.receipts) as [string,any][]){
  const endpoint=name==='submit'?'/api/submissions/submit':'/api/submissions/'+(name==='correction'?'received/':'')+fixture.submission+'/'+(name==='correction'?'request-revision':'resubmit');
  const response=await request.post(config.base_url+'/api'+endpoint,{headers:{Authorization:'Bearer '+(name==='correction'?cb:t),'Idempotency-Key':receipt.key},data:receipt.body});expect(response.status(),await response.text()).toBe(200);expect(await response.json()).toEqual(receipt.response);
 }
 await info.attach('restored-dossier',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
});
