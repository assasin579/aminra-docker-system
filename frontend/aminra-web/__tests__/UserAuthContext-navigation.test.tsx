import {act, renderHook, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {type ReactNode} from 'react';
import {UserAuthProvider, useUserAuth, type UserProfile} from '@/components/UserAuthContext';

const me: UserProfile = {id:'navigation-user', keycloak_sub:'navigation-user', email:'navigation@example.invalid', role:'business', status:'active', company_name:'Synthetic navigation', company_code:null, tenant_id:'navigation-user', is_owner:true};
const credential = 'header.' + btoa(JSON.stringify({sub:me.id,email:me.email})) + '.signature';
const fetchMock=vi.fn();
const wrapper=({children}:{children:ReactNode})=><UserAuthProvider>{children}</UserAuthProvider>;
beforeEach(()=>{localStorage.clear();sessionStorage.clear();localStorage.setItem('aminra_user_token',credential);fetchMock.mockReset();vi.stubGlobal('fetch',fetchMock);});
afterEach(()=>vi.unstubAllGlobals());

for(const outcome of ['aborted body','late valid body'] as const){
 it(`leaving the page invalidates a restore with ${outcome} without deleting the next document's credentials`,async()=>{
  let finish!:(value:UserProfile)=>void, fail!:(reason:unknown)=>void;
  const body=new Promise<UserProfile>((resolve,reject)=>{finish=resolve;fail=reject;});
  fetchMock.mockResolvedValue({ok:true,json:()=>body});
  const {result}=renderHook(()=>useUserAuth(),{wrapper});
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(1));
  act(()=>window.dispatchEvent(new PageTransitionEvent('pagehide')));
  await act(async()=>{if(outcome==='aborted body')fail(new DOMException('Navigation cancelled response','AbortError'));else finish(me);});
  expect(localStorage.getItem('aminra_user_token')).toBe(credential);
  expect(sessionStorage.getItem('aminra_auth_last_purge_reason')).toBeNull();
  expect(result.current.user).toBeNull();
 });
}

it('a page restored from browser history revalidates and rejects a revoked identity',async()=>{
 fetchMock.mockResolvedValueOnce(Response.json(me)).mockResolvedValueOnce(Response.json({detail:'Session revoked'},{status:401}));
 const {result}=renderHook(()=>useUserAuth(),{wrapper});
 await waitFor(()=>expect(result.current.user?.id).toBe(me.id));
 act(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));
 // Focus/visibility during departure must not restart a verification.
 act(()=>window.dispatchEvent(new Event('focus')));
 expect(fetchMock).toHaveBeenCalledTimes(1);
 act(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
 await waitFor(()=>expect(localStorage.getItem('aminra_user_token')).toBeNull());
 expect(result.current.user).toBeNull();
 expect(sessionStorage.getItem('aminra_auth_last_purge_reason')).toBe('auth_rejected');
});

it('a pending login cannot install credentials after its document has departed',async()=>{
 localStorage.clear();
 let finish!:(value:Response)=>void;
 fetchMock.mockReturnValue(new Promise<Response>(resolve=>{finish=resolve;}));
 const {result}=renderHook(()=>useUserAuth(),{wrapper});
 let login!:Promise<unknown>;
 act(()=>{login=result.current.loginBusiness(me.email,'synthetic-only').catch(error=>error);});
 act(()=>window.dispatchEvent(new PageTransitionEvent('pagehide')));
 await act(async()=>{finish(Response.json({access_token:credential,user:me}));await login;});
 expect(await login).toBeInstanceOf(Error);
 expect(localStorage.getItem('aminra_user_token')).toBeNull();
 expect(result.current.user).toBeNull();
});
