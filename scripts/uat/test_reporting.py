"""Regression checks for dangerous false-positive acceptance reports."""
import base64,csv,json,tempfile,unittest
from pathlib import Path
from report import generate
class ReportingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name);self.baseline=self.out/'baseline.csv'
  with self.baseline.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['id','type','name','case_id']);w.writeheader();w.writerows([
    {'id':'DOC-05','type':'Control','name':'Versions'},
    {'id':'DOC-05','type':'Control','case_id':'old-run-case','name':'Historical result'},
    {'id':'E2E-02','type':'E2E','name':'Correction journey'}])
  self.state={'run_id':'synthetic-test','cleanup':True}
 def tearDown(self):self.tmp.cleanup()
 def result(self,status='passed',classification='expected',title='case @DOC-05'):
  (self.out/'playwright.json').write_text(json.dumps({'suites':[{'specs':[{'title':title,'tests':[{'status':classification,'results':[{'status':status}]}]}]}]}))
  return generate(self.baseline,self.out,self.state)
 def test_no_results_does_not_pass_or_reuse_historical_result(self):
  r=generate(self.baseline,self.out,self.state);self.assertEqual(r['baseline_total'],2);self.assertEqual(r['gate'],'BLOCKED');self.assertEqual(r['execution_gate'],'FAIL')
 def test_subcase_success_does_not_promote_whole_control(self):
  r=self.result();self.assertEqual(r['execution_gate'],'PASS');self.assertEqual(r['controls'][0]['status'],'Blocked');self.assertEqual(r['controls'][0]['automation_coverage'],'Partial')
 def test_skipped_is_blocked(self):self.assertEqual(self.result('skipped')['case_counts'],{'BLOCKED':1})
 def test_flaky_is_not_a_clean_pass(self):self.assertEqual(self.result(classification='flaky')['execution_gate'],'FAIL')
 def test_failure_propagates_to_linked_control(self):self.assertEqual(self.result('failed')['controls'][0]['status'],'Fail')
 def test_cleanup_failure_prevents_success(self):
  self.state['cleanup']=False;self.assertEqual(self.result()['execution_gate'],'FAIL')
 def test_unknown_control_is_rejected(self):
  with self.assertRaises(ValueError):self.result(title='case @DOC-99')
 def test_only_reviewed_scope_exclusion_becomes_na(self):
  fields=['id','type','name','case_id','pilot_scope','reviewer','scope_reason']
  with self.baseline.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([
    {'id':'SCOPE-01','type':'Scope decision','pilot_scope':'Excluded','reviewer':'Owner','scope_reason':'Later phase'},
    {'id':'SCOPE-02','type':'Scope decision','pilot_scope':'Excluded'}])
  r=generate(self.baseline,self.out,self.state)
  self.assertEqual([c['status'] for c in r['controls']],['N/A','Blocked'])
 def test_report_escapes_user_content(self):
  self.result(title='<script>alert(1)</script> @DOC-05');self.assertNotIn('<script>',(self.out/'report.html').read_text())
 def test_inline_evidence_is_saved_under_generated_private_filename(self):
  raw=b'{"persisted": true}'
  attachment={'name':'../../report.html','contentType':'application/json','body':base64.b64encode(raw).decode()}
  (self.out/'playwright.json').write_text(json.dumps({'suites':[{'specs':[{'title':'case @DOC-05','tests':[{'status':'expected','results':[{'status':'passed','attachments':[attachment]}]}]}]}]}))
  r=generate(self.baseline,self.out,self.state);path=Path(r['cases'][0]['evidence'][0])
  self.assertEqual(path.parent,self.out/'inline-evidence');self.assertEqual(path.read_bytes(),raw)
  self.assertEqual(path.stat().st_mode & 0o777,0o600)
  self.assertIn('inline-evidence/0-0.json',(self.out/'report.html').read_text())
 def test_invalid_inline_evidence_is_not_silently_accepted(self):
  (self.out/'playwright.json').write_text(json.dumps({'suites':[{'specs':[{'title':'case @DOC-05','tests':[{'results':[{'status':'passed','attachments':[{'body':'not base64!'}]}]}]}]}]}))
  with self.assertRaises(ValueError):generate(self.baseline,self.out,self.state)
if __name__=='__main__':unittest.main()
