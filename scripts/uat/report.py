"""Evidence-based reporting. Missing, skipped, flaky and partial never become PASS."""
import base64, csv, html, json, re
from collections import Counter
from pathlib import Path
ID=re.compile(r'@(AUTH|ORG|CB|STD|PRD|SUP|TRC|DOC|DOS|SUB|REV|AUD|MOB|DEC|CERT|VER|SUR|APL|AI|DASH|NOT|ADM|DATA|UX|E2E)-\d{2}\b')
def generate(baseline:Path,output:Path,state:dict):
 with baseline.open(encoding='utf-8-sig') as source:
  rows=[r for r in csv.DictReader(source) if not r.get('case_id')]
 if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate baseline IDs')
 payload=json.loads((output/'playwright.json').read_text()) if (output/'playwright.json').exists() else {}
 cases=[]
 def evidence(results,case_index):
  paths=[]
  for result in results:
   for attachment in result.get('attachments',[]):
    if attachment.get('path'):
     paths.append(attachment['path']);continue
    if 'body' not in attachment:continue
    # JSON reporter embeds body attachments as base64. Keep filenames independent
    # of untrusted attachment names; source traces and credentials remain private.
    data=base64.b64decode(attachment['body'],validate=True)
    folder=output/'inline-evidence';folder.mkdir(mode=0o700,exist_ok=True)
    ext={'image/png':'.png','application/json':'.json','text/plain':'.txt'}.get(attachment.get('contentType'),'.bin')
    target=folder/(str(case_index)+'-'+str(len(paths))+ext);target.write_bytes(data);target.chmod(0o600)
    paths.append(str(target))
  return paths
 def walk(suites):
  for suite in suites:
   walk(suite.get('suites',[]))
   for spec in suite.get('specs',[]):
    for t in spec.get('tests',[]):
     results=t.get('results',[]);statuses=[r.get('status') for r in results]
     if 'skipped' in statuses or not statuses:status='BLOCKED'
     elif t.get('status')=='flaky' or (len(results)>1 and any(s!='passed' for s in statuses)):status='FLAKY'
     elif all(s=='passed' for s in statuses):status='PASS'
     else:status='FAIL'
     ids=re.findall(r'@([A-Z]+-\d{2})\b',spec['title'])
     cases.append({'surface':'api' if spec['title'].startswith('[API]') else 'browser','name':spec['title'],'project':t.get('projectName'),'status':status,
       'controls':ids,'file':spec.get('file'),'line':spec.get('line'),
       'evidence':evidence(results,len(cases)),
       'errors':[e.get('message','') for r in results for e in r.get('errors',[])]})
 walk(payload.get('suites',[]))
 known={r['id'] for r in rows};unknown={i for c in cases for i in c['controls'] if i not in known}
 if unknown:raise ValueError('Test references unknown baseline IDs: '+str(sorted(unknown)))
 controls=[]
 for row in rows:
  linked=[c for c in cases if row['id'] in c['controls']]
  bad=any(c['status']=='FAIL' for c in linked)
  excluded=row['type']=='Scope decision' and row.get('pilot_scope')=='Excluded' and bool(row.get('reviewer')) and bool(row.get('scope_reason'))
  controls.append({**row,'status':'N/A' if excluded else ('Fail' if bad else 'Blocked'),
    'automation_coverage':'Partial' if linked else 'None',
    'reason':row['scope_reason'] if excluded else ('Executable subcases recorded; full control acceptance is not yet established' if linked else 'No maintained executable case mapped yet; scope/requirements need assessment'),
    'case_names':[c['name'] for c in linked]})
 counts=dict(Counter(c['status'] for c in cases));execution='PASS' if cases and all(c['status']=='PASS' for c in cases) and state.get('cleanup') and not state.get('error') else 'FAIL'
 report={'run':state,'case_counts':counts,'execution_gate':execution,'gate':'FAIL' if any(c['status'] in ('FAIL','FLAKY') for c in cases) else 'BLOCKED',
  'baseline_total':len(rows),'controls':controls,'cases':cases,'scope':'Automated subcases; no business/pilot sign-off'}
 (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 with (output/'coverage.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=['id','type','group','name','status','automation_coverage','reason']);writer.writeheader();writer.writerows({k:r.get(k,'') for k in writer.fieldnames} for r in controls)
 esc=lambda v:html.escape(str(v))
 def evidence_links(paths):
  links=[]
  for i,p in enumerate(paths):
   try:relative=Path(p).resolve().relative_to(output.resolve())
   except ValueError:continue
   links.append('<a href="'+esc(relative)+'">Evidence '+str(i+1)+'</a>')
  return ' · '.join(links)
 body=''.join('<tr><td>'+esc(c['name'])+'</td><td>'+esc(c['status'])+'</td><td>'+esc(', '.join(c['controls']))+'</td><td>'+evidence_links(c['evidence'])+'</td></tr>' for c in cases)
 coverage=''.join('<tr><td>'+esc(c['id'])+'</td><td>'+esc(c['name'])+'</td><td>'+esc(c['status'])+'</td><td>'+esc(c['automation_coverage'])+'</td><td>'+esc(c['reason'])+'</td></tr>' for c in controls)
 (output/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>AMINRA UAT</title><style>body{font:16px system-ui;margin:32px;max-width:1400px}table{border-collapse:collapse;width:100%}td,th{padding:10px;border:1px solid #ddd;text-align:left}h1{color:#10294a}</style><h1>AMINRA automated UAT</h1><p>Run '+esc(state['run_id'])+'</p><p>Executable subcases: '+execution+'; full baseline: '+report['gate']+'. No pilot sign-off.</p><p>'+esc(counts)+'</p><p><a href="browser-report/index.html">Open detailed browser report and evidence</a></p><h2>Executed cases</h2><table><tr><th>Case</th><th>Status</th><th>Baseline references</th><th>Evidence</th></tr>'+body+'</table><h2>Full baseline coverage ('+str(len(rows))+')</h2><table><tr><th>ID</th><th>Requirement</th><th>Status</th><th>Coverage</th><th>Reason</th></tr>'+coverage+'</table>')
 return report
