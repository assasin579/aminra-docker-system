import { test, expect, type Page } from '@playwright/test';
import { config, login, control } from './helpers';

async function seedEvaluation(page:Page,summary:string){
 const actor=config.actors.bizA;const filename=config.run_id+'-private-analysis.pdf';
 const key=['aminra_private:v1',actor.id,actor.tenant_id,'evaluation',''].map(encodeURIComponent).join(':');
 await page.evaluate(({key,filename,summary})=>sessionStorage.setItem(key,JSON.stringify({report:{filename,doc_type:'halal_policy',doc_type_label:'Policy',word_count:100,standards_found:0,compliance_score:50,overall_status:'needs_review',summary,issues:[],strengths:[],recommendations:[],standards_checked:[],gap_analysis:null,risk_flags:[],citations:[],document_save_status:'not_applicable'}})),{key,filename,summary});
 await page.goto('/upload');await expect(page.getByRole('heading',{name:filename,exact:true})).toBeVisible();return filename;
}

test('PRIVATE-EXPORT-HTML @DAT-01 @RPT-06 exported AI and review text cannot execute scripts or access the opener',async({page,context})=>{
 await login(page,'bizA');const attack='<img src=x onerror="window.__reportInjected=1"><script>window.__reportInjected=1</script>';
 await seedEvaluation(page,attack);await page.getByRole('button',{name:/^↓\s*Xuất báo cáo$/}).click();
 const popupPromise=context.waitForEvent('page');await page.getByRole('button',{name:/^↓\s*In \/ Lưu PDF$/}).click();const popup=await popupPromise;
 await expect(popup.getByRole('heading',{name:'Báo cáo Đánh giá Halal Compliance'})).toBeVisible();
 expect(await popup.locator('script,img,[onerror]').count()).toBe(0);expect(await popup.locator('body').textContent()).toContain(attack);
 expect(await popup.evaluate(()=>window.opener===null)).toBe(true);expect(await popup.evaluate(()=>('__reportInjected' in window))).toBe(false);await popup.close();
});

test('PRIVATE-CLIENT-LOGOUT @AUTH-04 @DAT-01 logout clears private history and the legacy offline database before the next account uses the browser',async({page})=>{
 await login(page,'bizA');const name=await seedEvaluation(page,'Private synthetic organization A analysis');
 await page.evaluate(async()=>{
  localStorage.setItem('aminra_full_report_legacy.pdf','Private synthetic A legacy');
  await new Promise<void>((resolve,reject)=>{const r=indexedDB.open('aminra-offline',1);r.onupgradeneeded=()=>r.result.createObjectStore('sync-queue',{keyPath:'id'});r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result;const tx=db.transaction('sync-queue','readwrite');tx.objectStore('sync-queue').put({id:1,body:'Private synthetic A offline',headers:{Authorization:'Bearer synthetic-previous-user'}});tx.oncomplete=()=>{db.close();resolve();};};});
 });
 await page.getByRole('button').filter({has:page.getByText(config.actors.bizA.email,{exact:true})}).click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
 await expect(page.getByRole('heading',{name,exact:true})).toHaveCount(0);
 await expect.poll(()=>page.evaluate(async()=>({privateKeys:[...Object.keys(localStorage),...Object.keys(sessionStorage)].filter(key=>key.startsWith('aminra_private')||key.startsWith('aminra_full_report_')||key.startsWith('aminra_eval_')),offlineDatabase:(await indexedDB.databases()).some(db=>db.name==='aminra-offline')}))).toEqual({privateKeys:[],offlineDatabase:false});
 await login(page,'bizB');await page.goto('/upload');await expect(page.getByText('Private synthetic organization A analysis',{exact:true})).toHaveCount(0);await expect(page.getByRole('heading',{name,exact:true})).toHaveCount(0);
});


test('PRIVATE-AUTHORITY-DOWNGRADE @AUTH-05 @CB-05 current server roles remove admin UI and cached descendants while the old JWT still contains admin',async({page,context,request})=>{
 control('keycloak_authority',{actor:'admin',action:'grant_cb_role'});
 try{
  const t=await login(page,'admin');await page.goto('/admin');await expect(page.getByRole('link',{name:'Admin Panel',exact:true})).toBeVisible();
  const other=await context.newPage();await other.goto('/offline.html');
  control('keycloak_authority',{actor:'admin',action:'remove_role'});
  await expect.poll(async()=>{const r=await request.get(config.base_url+'/api/auth/me',{headers:{Authorization:'Bearer '+t}});expect(r.status()).toBe(200);const me=await r.json();return me.realm_roles.includes('platform_admin');},{timeout:10000}).toBe(false);
  await page.bringToFront();
  await expect(page.getByRole('link',{name:'Admin Panel',exact:true})).toHaveCount(0);
  await expect(page.getByText('Không có quyền truy cập',{exact:true})).toBeVisible();
  await other.close();
 }finally{control('keycloak_authority',{actor:'admin',action:'restore'});}
});
