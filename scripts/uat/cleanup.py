#!/usr/bin/env python3
"""Recover resources after a killed UAT runner, only with exact run labels."""
import argparse,json,re,subprocess
from pathlib import Path
LABEL='io.aminra.uat.run'
def cleanup(path):
 manifest=json.loads(Path(path).read_text());run=manifest['run_id']
 if not re.fullmatch(r'uat-\d{8}-[a-f0-9]{8}',run):raise ValueError('Invalid UAT run id')
 errors=[]
 for name in reversed(manifest['containers']):
  if not re.fullmatch(re.escape(run)+r'-(postgres|keycloak|backend|frontend|redis)',name):raise ValueError('Invalid resource name')
  r=subprocess.run(['docker','inspect',name],capture_output=True)
  if r.returncode:continue
  if json.loads(r.stdout)[0]['Config'].get('Labels',{}).get(LABEL)!=run:raise ValueError('Resource label mismatch')
  if subprocess.run(['docker','rm','-fv',name],capture_output=True).returncode:errors.append(name)
 if manifest['network']!=run:raise ValueError('Network name mismatch')
 r=subprocess.run(['docker','network','inspect',run],capture_output=True)
 if not r.returncode:
  if json.loads(r.stdout)[0].get('Labels',{}).get(LABEL)!=run:raise ValueError('Network label mismatch')
  if subprocess.run(['docker','network','rm',run],capture_output=True).returncode:errors.append(run)
 if errors:raise RuntimeError('Cleanup failed: '+','.join(errors))
 return {'run_id':run,'cleanup':True}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('resources');a=p.parse_args();print(json.dumps(cleanup(a.resources)))
