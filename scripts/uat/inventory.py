#!/usr/bin/env python3
"""Export all baseline controls, decisions and journeys without changing their status."""
import argparse,csv,hashlib,json,re
from collections import Counter
from pathlib import Path

def inventory(baseline,root):
 baseline=Path(baseline)
 with baseline.open(encoding='utf-8-sig') as f:rows=[r for r in csv.DictReader(f) if not r.get('case_id')]
 if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate baseline definition')
 cases={}
 for spec in Path(root).glob('*.spec.ts'):
  for title in re.findall(r"test\('([^']+)'",spec.read_text()):
   for control in re.findall(r'@([A-Z]+-\d{2})\b',title):cases.setdefault(control,[]).append({'file':spec.name,'case':title,'surface':'api' if title.startswith('[API]') else 'browser'})
 return {'baseline_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),'types':dict(Counter(r['type'] for r in rows)),
  'controls':[{**{k:r.get(k,'') for k in ('id','type','group','name','expected','pilot_scope','priority')},'candidate_cases':cases.get(r['id'],[]),'status':'N/A' if r['type']=='Scope decision' and r.get('pilot_scope')=='Excluded' else 'Not run','scope_decision_required':r['type']=='Scope decision' and r.get('pilot_scope')!='Excluded'} for r in rows]}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline');p.add_argument('--specs',default='frontend/aminra-web/uat');p.add_argument('--output',required=True);a=p.parse_args();result=inventory(a.baseline,a.specs);Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps(result['types']))
