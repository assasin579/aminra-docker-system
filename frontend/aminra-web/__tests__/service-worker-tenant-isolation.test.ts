import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { expect, it, vi } from 'vitest';

it('never stores an authenticated audit response or falls back to another identity\'s cached response', async () => {
 const handlers: Record<string,(event: unknown)=>void>={};
 const put=vi.fn(),match=vi.fn(async()=>Response.json({secret:'tenant-a'}));
 const network=vi.fn().mockResolvedValueOnce(Response.json({secret:'tenant-a'})).mockRejectedValueOnce(new TypeError('Offline'));
 runInNewContext(readFileSync('public/sw.js','utf8'),{
  self:{location:{origin:'https://example.invalid'},addEventListener:(name:string,fn:(event:unknown)=>void)=>{handlers[name]=fn;}},
  URL,fetch:network,Response,caches:{open:async()=>({put}),match},
 });
 function request(token:string){let result!:Promise<Response>;handlers.fetch({request:new Request('https://example.invalid/api/api/audits/private-visit',{headers:{Authorization:'Bearer '+token}}),respondWith:(promise:Promise<Response>)=>{result=promise;}});return result;}
 expect(await (await request('synthetic-a')).json()).toEqual({secret:'tenant-a'});
 await expect(request('synthetic-b')).rejects.toThrow('Offline');
 expect(put).not.toHaveBeenCalled();expect(match).not.toHaveBeenCalled();
});
