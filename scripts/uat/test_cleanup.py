import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cleanup import cleanup
class CleanupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'resources.json'
 def tearDown(self):self.tmp.cleanup()
 def test_manifest_cannot_target_live_container(self):
  self.path.write_text(json.dumps({'run_id':'uat-20261031-12345678','containers':['aminra-docker-system-aminra-backend-1'],'network':'uat-20261031-12345678'}))
  with patch('cleanup.subprocess.run') as command:
   with self.assertRaises(ValueError):cleanup(self.path)
   command.assert_not_called()
 def test_similar_named_container_with_wrong_label_is_not_deleted(self):
  self.path.write_text(json.dumps({'run_id':'uat-20261031-12345678','containers':['uat-20261031-12345678-backend'],'network':'uat-20261031-12345678'}))
  with patch('cleanup.subprocess.run') as command:
   command.return_value.returncode=0;command.return_value.stdout=json.dumps([{'Config':{'Labels':{'io.aminra.uat.run':'different'}}}]).encode()
   with self.assertRaises(ValueError):cleanup(self.path)
   self.assertEqual(command.call_count,1)
 def test_invalid_run_identity_never_invokes_docker(self):
  self.path.write_text(json.dumps({'run_id':'production','containers':[],'network':'production'}))
  with patch('cleanup.subprocess.run') as command:
   with self.assertRaises(ValueError):cleanup(self.path)
   command.assert_not_called()
