import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {expect,it,vi} from 'vitest';
const layout=readFileSync(join(process.cwd(),'app/layout.tsx'),'utf8');
const script=layout.match(/__html: `([\s\S]*?)`,/)?.[1];
if(!script)throw new Error('Root service-worker bootstrap script missing');
function bootstrap(controlled:boolean,path='/business/login'){
 const windowEvents=new Map<string,()=>void>(),workerEvents=new Map<string,()=>void>();
 const reload=vi.fn(),update=vi.fn().mockResolvedValue(undefined),postMessage=vi.fn();
 const serviceWorker={controller:controlled?{}:null as object|null,register:vi.fn().mockResolvedValue({update,waiting:{postMessage}}),addEventListener:(name:string,fn:()=>void)=>workerEvents.set(name,fn)};
 const window={location:{pathname:path,reload},addEventListener:(name:string,fn:()=>void)=>windowEvents.set(name,fn)};
 new Function('window','navigator',script!)(window,{serviceWorker});windowEvents.get('load')!();
 return {reload,serviceWorker,change:()=>workerEvents.get('controllerchange')!(),update,postMessage};
}
for(const path of ['/business/login','/provider/login','/dashboard/business','/admin']){
 it(`initial worker claim on ${path} does not reload a live form or page`,()=>{
  const app=bootstrap(false,path);app.serviceWorker.controller={};app.change();expect(app.reload).not.toHaveBeenCalled();
 });
}
it('a subsequent worker replacement still reloads an auth-critical page exactly once',()=>{
 const app=bootstrap(false);app.serviceWorker.controller={};app.change();expect(app.reload).not.toHaveBeenCalled();
 app.serviceWorker.controller={};app.change();app.change();expect(app.reload).toHaveBeenCalledTimes(1);
});
it('an already controlled page still reloads once for a worker upgrade',()=>{
 const app=bootstrap(true);app.serviceWorker.controller={};app.change();app.change();expect(app.reload).toHaveBeenCalledTimes(1);
});
for(const path of ['/auth/callback','/documents'])it(`worker upgrade does not force navigation on ${path}`,()=>{
 const app=bootstrap(true,path);app.serviceWorker.controller={};app.change();expect(app.reload).not.toHaveBeenCalled();
});
