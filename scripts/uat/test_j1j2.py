import json,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from j1j2 import MANIFEST,generate
class AcceptanceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)
  names=sorted({k for _,_,cases,_ in MANIFEST for k in cases})
  self.report={'run':{'run_id':'unit-fixture','cleanup':True,'images':{'backend':'unit-image'},'schema_head':'unit-schema','suite_manifest':{'test':'unit-hash'}},'cases':[{'name':name+' unit case','status':'PASS'} for name in names]}
  xml=ET.Element('testsuite')
  for name in sorted({n for _,_,_,tests in MANIFEST for n in tests}):
   variants=['[True]','[False]'] if name=='reused_document_does_not_borrow_another_dossier_review_context' else ['']
   for variant in variants:ET.SubElement(xml,'testcase',name='test_'+name+variant)
  ET.ElementTree(xml).write(self.out/'database.xml')
  (self.out/'runtime-checks.json').write_text(json.dumps({'guard_055':True,'guard_057':True,'schema_head_preserved':True,'app_role_least_privilege':True,'images_match_source_revision':True}))
 def tearDown(self):self.tmp.cleanup()
 def test_full_required_evidence_maps_exactly_eighteen_criteria(self):
  r=generate(self.report,self.out);self.assertEqual((r['passed'],r['total'],r['gate']),(18,18,'PASS'));self.assertEqual(len({c['id'] for c in r['criteria']}),18)
 def test_missing_browser_case_cannot_pass_on_database_alone(self):
  self.report['cases']=[c for c in self.report['cases'] if not c['name'].startswith('J1-DASHBOARD-RACE ')]
  r=generate(self.report,self.out);self.assertEqual(next(c['status'] for c in r['criteria'] if c['id']=='J1-A08'),'BLOCKED')
 def test_failing_case_propagates_to_related_criteria(self):
  next(c for c in self.report['cases'] if c['name'].startswith('JOURNEY-01 '))['status']='FAIL'
  self.assertEqual(generate(self.report,self.out)['gate'],'FAIL')
 def test_skipped_database_case_is_not_a_pass(self):
  xml=ET.parse(self.out/'database.xml');ET.SubElement(xml.find('.//testcase'),'skipped');xml.write(self.out/'database.xml');self.assertNotEqual(generate(self.report,self.out)['gate'],'PASS')
 def test_missing_parametrized_branch_is_blocked(self):
  xml=ET.parse(self.out/'database.xml');root=xml.getroot()
  for c in list(root):
   if c.attrib['name'].endswith('[False]'):root.remove(c)
  xml.write(self.out/'database.xml');self.assertNotEqual(generate(self.report,self.out)['gate'],'PASS')
 def test_false_guard_and_missing_provenance_block_acceptance(self):
  (self.out/'runtime-checks.json').write_text(json.dumps({'guard_055':False,'guard_057':True,'schema_head_preserved':True,'app_role_least_privilege':True,'images_match_source_revision':True}));r=generate(self.report,self.out);self.assertEqual(next(c['status'] for c in r['criteria'] if c['id']=='X-A02'),'FAIL')
  self.report['run']['suite_manifest']={};self.assertEqual(generate(self.report,self.out)['passed'],0)
 def test_cleanup_failure_blocks_all_criteria(self):
  self.report['run']['cleanup']=False;self.assertEqual(generate(self.report,self.out)['passed'],0)

 def test_unmapped_failure_cannot_hide_behind_eighteen_passes(self):
  self.report['cases'].append({'name':'extra regression','status':'FAIL'})
  self.assertEqual(generate(self.report,self.out)['gate'],'FAIL')
 def test_source_changed_during_run_blocks_acceptance(self):
  self.report['run']['test_source_unchanged']=False
  self.assertEqual(generate(self.report,self.out)['passed'],0)
