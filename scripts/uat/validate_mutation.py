#!/usr/bin/env python3
"""Verify a deliberately weakened test image was rejected for the expected reason."""
import argparse,json,re
from pathlib import Path

def validate(path):
 report=json.loads(Path(path).read_text())
 cases=[c for c in report['cases'] if 'PERM-01' in c['name']]
 if len(cases)!=1 or cases[0]['status']!='FAIL':raise ValueError('Authorization mutant did not fail the required case')
 error=re.sub(r'\x1b\[[0-9;]*m','', '\n'.join(cases[0]['errors']))
 if 'Expected: 403' not in error or 'Received: 200' not in error:raise ValueError('Mutation failed for an unrelated infrastructure/test reason')
 if not report['run']['cleanup'] or not report['run'].get('pre_existing_runtimes_unchanged'):raise ValueError('Mutation cleanup/isolation unverified')
 return {'mutation':'remove-promote-guard','detected':True,'expected':403,'observed':200,'cleanup':True}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('report');a=p.parse_args();print(json.dumps(validate(a.report)))
