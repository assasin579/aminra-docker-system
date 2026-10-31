import tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from run import execute, storage_preflight

class StoragePreflightTests(unittest.TestCase):
 def test_insufficient_capacity_stops_before_run_or_docker_resources(self):
  with patch('run.shutil.disk_usage',return_value=SimpleNamespace(free=34*1024*1024)),patch('run.Run') as run:
   with self.assertRaisesRegex(RuntimeError,'disk-backed TMPDIR'):
    execute(SimpleNamespace(output='/nonexistent/uat-output'))
   run.assert_not_called()

 def test_checks_evidence_volume_separately_from_temporary_volume(self):
  with tempfile.TemporaryDirectory() as output,patch('run.shutil.disk_usage',side_effect=[SimpleNamespace(free=1024**3),SimpleNamespace(free=1)]):
   with self.assertRaisesRegex(RuntimeError,'evidence workspace'):
    storage_preflight(str(Path(output)/'not-created'))

 def test_sufficient_capacity_accepts_not_yet_created_evidence_directory(self):
  with tempfile.TemporaryDirectory() as output,patch('run.shutil.disk_usage',return_value=SimpleNamespace(free=1024**3)) as usage:
   storage_preflight(str(Path(output)/'not-created'))
   self.assertEqual(usage.call_count,2)
