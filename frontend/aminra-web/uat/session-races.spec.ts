import { test, expect, type Page, type Route } from '@playwright/test';
import { api, config, control, login, token } from './helpers';

function deferred() {
 let resolve!: () => void;
 const promise = new Promise<void>(done => { resolve = done; });
 return { promise, resolve };
}

async function publish(page:Page, accessToken:string, profile:unknown) {
 await page.evaluate(({accessToken,profile}) => {
  localStorage.setItem('aminra_user_token',accessToken);
  localStorage.setItem('aminra_user_profile',JSON.stringify(profile));
  document.cookie='aminra_session=1; path=/; SameSite=Lax';
  window.dispatchEvent(new Event('aminra:auth-session-changed'));
 },{accessToken,profile});
}

async function storedIdentity(page:Page) {
 return page.evaluate(() => {
  const profile=JSON.parse(localStorage.getItem('aminra_user_profile') || 'null');
  return {id:profile?.id,token:localStorage.getItem('aminra_user_token')};
 });
}

// Delay delivery, not backend validation. A response may be aborted by the
// browser once the session changes; that cancellation is expected protection.
async function deliver(route:Route, response:Awaited<ReturnType<Route['fetch']>>) {
 try { await route.fulfill({response}); }
 catch(error) {
  if(!/Target closed|Target page, context or browser has been closed|Invalid InterceptionId|already handled|interception.*not found/i.test(String(error))) throw error;
 }
}

for(const operation of ['restore','refresh'] as const) {
for(const outcome of ['success','rejected'] as const) {
 test(`LATE-${operation.toUpperCase()}-${outcome.toUpperCase()} @AUTH-04 @AUTH-06 delayed old verification cannot overwrite or purge the new account`,async({page,context,request}) => {
  const old=await token(request,'bizA'),next=await token(request,'bizB');
  const oldProfile=await api(request,old,'/auth/me'),nextProfile=await api(request,next,'/auth/me');
  const candidate=operation==='refresh'||outcome==='success'?old:old.slice(0,-8)+'invalid0';
  await page.goto('/offline.html');await publish(page,candidate,oldProfile);
  if(operation==='refresh') {
   await page.goto('/documents');
   await expect(page.getByText(config.actors.bizA.email,{exact:true})).toBeVisible();
  }
  const captured=deferred(),release=deferred(),finished=deferred();let intercepted=false;
  await page.route('**/api/auth/me',async route => {
   if(intercepted || route.request().headers().authorization!=='Bearer '+candidate) return route.continue();
   intercepted=true;
   const response=await route.fetch();expect(response.status()).toBe(operation==='refresh'||outcome==='success'?200:401);
   captured.resolve();await release.promise;
   try {
    if(operation==='refresh'&&outcome==='rejected') await route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Synthetic delayed rejection'})});
    else await deliver(route,response);
   } finally { finished.resolve(); }
  });
  try {
   if(operation==='restore') await page.goto('/documents');
   else await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
   await captured.promise;
   const other=await context.newPage();await other.goto('/offline.html');await publish(other,next,nextProfile);
   await expect.poll(()=>storedIdentity(page)).toEqual({id:config.actors.bizB.id,token:next});
   await expect(page.getByText(config.actors.bizB.email,{exact:true})).toBeVisible();
   release.resolve();await finished.promise;
   await expect.poll(()=>storedIdentity(page)).toEqual({id:config.actors.bizB.id,token:next});
   await expect(page.getByText(config.actors.bizA.email,{exact:true})).toHaveCount(0);
   await page.reload();await expect(page.getByText(config.actors.bizB.email,{exact:true})).toBeVisible();
   await other.close();
  } finally { release.resolve(); }
 });
}

}

for(const rejected of [false,true]) {
 test(`ADMIN-CANDIDATE-${rejected?'REJECT':'VERIFY'} @AUTH-04 @AUTH-05 candidate admin storage cannot render admin UI before server verification`,async({page,request}) => {
  const valid=await token(request,'admin'),profile=await api(request,valid,'/auth/me');
  const candidate=rejected?valid.slice(0,-8)+'invalid0':valid;
  await page.goto('/offline.html');await publish(page,candidate,{...profile,realm_roles:['platform_admin']});
  const captured=deferred(),release=deferred(),finished=deferred();let intercepted=false;
  const privileged:string[]=[];
  page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/admin/')) privileged.push(r.url());});
  await page.route('**/api/auth/me',async route => {
   if(intercepted) return route.continue();intercepted=true;
   const response=await route.fetch();expect(response.status()).toBe(rejected?401:200);
   captured.resolve();await release.promise;
   try { await deliver(route,response); } finally { finished.resolve(); }
  });
  try {
   await page.goto('/admin');await captured.promise;
   await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toHaveCount(0);expect(privileged).toEqual([]);
   release.resolve();await finished.promise;
   if(rejected) {
    await expect.poll(()=>page.evaluate(()=>localStorage.getItem('aminra_user_token'))).toBeNull();
    await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toHaveCount(0);expect(privileged).toEqual([]);
   } else {
    await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toBeVisible();
    await expect.poll(()=>privileged.length).toBeGreaterThan(0);
   }
  } finally { release.resolve(); }
 });
}

test('LATE-LOGIN @AUTH-04 @AUTH-06 a delayed password response cannot replace a newer account published in another tab',async({page,context,request}) => {
 const next=await token(request,'bizB'),profile=await api(request,next,'/auth/me');
 const captured=deferred(),release=deferred(),finished=deferred();
 await page.route('**/api/auth/login',async route => {
  const response=await route.fetch();expect(response.status()).toBe(200);
  captured.resolve();await release.promise;
  try { await deliver(route,response); } finally { finished.resolve(); }
 });
 try {
  await page.goto('/business/login');
  await page.locator('input[type=email]').fill(config.actors.bizA.email);
  await page.locator('input[type=password]').fill(config.actors.bizA.password);
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await captured.promise;
  const other=await context.newPage();await other.goto('/offline.html');
  const verified=page.waitForResponse(r=>r.url().endsWith('/api/auth/me')&&r.request().headers().authorization==='Bearer '+next);
  await publish(other,next,profile);expect((await verified).status()).toBe(200);
  await expect(page.locator('input[type=email]')).toHaveValue('');
  release.resolve();await finished.promise;
  await expect.poll(()=>storedIdentity(page)).toEqual({id:config.actors.bizB.id,token:next});
  await page.goto('/documents');await expect(page.getByText(config.actors.bizB.email,{exact:true})).toBeVisible();
  await other.close();
 } finally { release.resolve(); }
});

test('ADMIN-DOWNGRADE-TAB @AUTH-04 @AUTH-05 verified admin subtree disappears when another tab changes to a non-admin account',async({page,context,request}) => {
 const admin=await token(request,'admin'),adminProfile=await api(request,admin,'/auth/me');
 const next=await token(request,'cbX'),profile=await api(request,next,'/auth/me');
 await page.goto('/offline.html');await publish(page,admin,adminProfile);await page.goto('/admin');
 await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toBeVisible();
 await page.evaluate(()=>caches.open('aminra-admin-race').then(c=>c.put('/private-admin-race',new Response('synthetic admin cache'))));
 const other=await context.newPage();await other.goto('/offline.html');await publish(other,next,{...profile,realm_roles:['platform_admin']});
 await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'Không có quyền truy cập',exact:true})).toBeVisible();
 await expect.poll(()=>storedIdentity(page)).toEqual({id:config.actors.cbX.id,token:next});
 await expect.poll(()=>page.evaluate(()=>caches.keys())).not.toContain('aminra-admin-race');
 await page.reload();await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'Không có quyền truy cập',exact:true})).toBeVisible();
 const denied=await request.get(config.base_url+'/api/admin/templates/halal_policy/files',{headers:{Authorization:'Bearer '+next}});expect(denied.status()).toBe(403);
 await other.close();
});

test('ADMIN-SAME-TOKEN-DOWNGRADE @AUTH-04 @AUTH-05 current server roles remove admin UI and cache while the JWT still claims admin',async({page,request}) => {
 control('keycloak_authority',{actor:'admin',action:'grant_cb_role'});
 try {
  const credential=await token(request,'admin'),profile=await api(request,credential,'/auth/me');
  await page.goto('/offline.html');await publish(page,credential,profile);await page.goto('/admin');
  await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toBeVisible();
  await page.evaluate(()=>caches.open('aminra-admin-downgrade').then(c=>c.put('/private-admin-downgrade',new Response('synthetic old admin data'))));
  control('keycloak_authority',{actor:'admin',action:'remove_role'});
  await expect.poll(()=>page.evaluate(()=>{
   window.dispatchEvent(new Event('focus'));
   const p=JSON.parse(localStorage.getItem('aminra_user_profile') || 'null');
   return Array.isArray(p?.realm_roles)?p.realm_roles.filter((r:string)=>['platform_admin','cb_admin'].includes(r)).sort():null;
  }),{timeout:15000}).toEqual(['cb_admin']);
  await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Không có quyền truy cập',exact:true})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>caches.keys())).not.toContain('aminra-admin-downgrade');
  expect((await storedIdentity(page)).token).toBe(credential);
  const denied=await request.get(config.base_url+'/api/admin/templates/halal_policy/files',{headers:{Authorization:'Bearer '+credential}});expect(denied.status()).toBe(403);
 } finally { control('keycloak_authority',{actor:'admin',action:'restore'}); }
});

test('LATE-LOGOUT-CLEANUP @AUTH-04 @AUTH-06 old asynchronous cache cleanup cannot purge a newer login in another tab',async({page,context})=>{
 await login(page,'bizA');
 await page.evaluate(()=>{
  const original=caches.keys.bind(caches);
  const state={held:false,finished:false,release:()=>{}};
  (window as unknown as {logoutRace:typeof state}).logoutRace=state;
  caches.keys=async()=>{
   if(state.held) return original();
   state.held=true;
   await new Promise<void>(resolve=>{state.release=resolve;});
   const result=await original();state.finished=true;return result;
  };
 });
 try {
  await page.getByRole('button').filter({has:page.getByText(config.actors.bizA.email,{exact:true})}).click();
  await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>(window as unknown as {logoutRace:{held:boolean}}).logoutRace.held)).toBe(true);
  const other=await context.newPage();const next=await login(other,'bizB');
  await expect.poll(()=>storedIdentity(page)).toEqual({id:config.actors.bizB.id,token:next});
  await page.evaluate(()=>(window as unknown as {logoutRace:{release:()=>void}}).logoutRace.release());
  await expect.poll(()=>page.evaluate(()=>(window as unknown as {logoutRace:{finished:boolean}}).logoutRace.finished)).toBe(true);
  await expect.poll(()=>storedIdentity(page)).toEqual({id:config.actors.bizB.id,token:next});
  await page.goto('/documents');
  await expect(page.getByText(config.actors.bizB.email,{exact:true})).toBeVisible();
  await expect(page.getByText(config.actors.bizA.email,{exact:true})).toHaveCount(0);
  await page.reload();await expect(page.getByText(config.actors.bizB.email,{exact:true})).toBeVisible();
  await other.close();
 } finally {
  await page.evaluate(()=>(window as unknown as {logoutRace?:{release:()=>void}}).logoutRace?.release()).catch(()=>{});
 }
});

test('ADMIN-VISIBLE-REVOCATION @AUTH-05 current visible admin loses authority through scheduled verification without synthetic focus',async({page,request})=>{
 control('keycloak_authority',{actor:'admin',action:'grant_cb_role'});
 try {
  const credential=await token(request,'admin'),profile=await api(request,credential,'/auth/me');
  await page.goto('/offline.html');await publish(page,credential,profile);await page.goto('/admin');
  await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.visibilityState)).toBe('visible');
  await page.evaluate(()=>caches.open('aminra-visible-admin').then(c=>c.put('/private-visible-admin',new Response('synthetic privileged state'))));
  control('keycloak_authority',{actor:'admin',action:'remove_role'});
  await expect(page.getByRole('heading',{name:'Admin Panel',exact:true})).toHaveCount(0,{timeout:25000});
  await expect(page.getByRole('heading',{name:'Không có quyền truy cập',exact:true})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>caches.keys())).not.toContain('aminra-visible-admin');
  expect((await storedIdentity(page)).token).toBe(credential);
  const denied=await request.get(config.base_url+'/api/admin/templates/halal_policy/files',{headers:{Authorization:'Bearer '+credential}});expect(denied.status()).toBe(403);
 } finally {control('keycloak_authority',{actor:'admin',action:'restore'});}
});
