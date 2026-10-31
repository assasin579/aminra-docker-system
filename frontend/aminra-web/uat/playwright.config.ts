import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const file=process.env.UAT_CONFIG;
if(!file) throw new Error('Use scripts/uat/run.py; UAT_CONFIG is required');
const config=JSON.parse(fs.readFileSync(file,'utf8'));
const url=new URL(config.base_url);
if(url.protocol!=='http:' || !['127.0.0.1','localhost'].includes(url.hostname)) throw new Error('Full UAT refuses non-loopback targets');
if(!/^uat-\d{8}-[a-f0-9]{8}$/.test(config.run_id)) throw new Error('Invalid isolated run identity');
const output=process.env.UAT_OUTPUT!;
export default defineConfig({
 testDir:'.',testMatch:process.env.UAT_RECOVERY==='1'?'recovery.spec.ts':(process.env.UAT_SUITE==='j1j2'?['journeys.spec.ts','boundaries.spec.ts','j1j2.spec.ts']:(process.env.UAT_SUITE==='core'?['journeys.spec.ts','boundaries.spec.ts']:['journeys.spec.ts','boundaries.spec.ts','extended.spec.ts','audit-boundaries.spec.ts','certification.spec.ts','authorization-concurrency.spec.ts','private-artifacts.spec.ts','service-worker-isolation.spec.ts','private-client-ui.spec.ts','session-races.spec.ts'])),timeout:180_000,expect:{timeout:15_000},
 globalTimeout:15*60*1000,fullyParallel:false,workers:1,retries:0,forbidOnly:true,
 outputDir:path.join(output,'artifacts'),
 reporter:[['list'],['json',{outputFile:path.join(output,'playwright.json')}],['html',{outputFolder:path.join(output,'browser-report'),open:'never'}]],
 use:{baseURL:config.base_url,trace:'retain-on-failure',screenshot:'only-on-failure',video:'retain-on-failure',actionTimeout:15000,serviceWorkers:'block'},
 projects:[{name:'desktop',use:{...devices['Desktop Chrome'],viewport:{width:1440,height:1000}}},
 {name:'mobile',use:{...devices['Pixel 7']}},{name:'firefox',use:{...devices['Desktop Firefox']}},{name:'webkit',use:{...devices['Desktop Safari']}}]
});
