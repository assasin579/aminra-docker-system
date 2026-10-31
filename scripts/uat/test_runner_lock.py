"""Prove overlapping invocations are rejected before Docker setup."""
import tempfile, unittest
from pathlib import Path
from run import execution_lock

class RunnerLockTests(unittest.TestCase):
 def test_second_invocation_is_rejected_and_lock_is_reusable(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'lock'
   with execution_lock(path):
    with self.assertRaisesRegex(RuntimeError,'Another isolated UAT run'):
     with execution_lock(path):self.fail('overlapping invocation accepted')
   with execution_lock(path):pass
 def test_exception_releases_lock(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'lock'
   with self.assertRaisesRegex(ValueError,'interrupted'):
    with execution_lock(path):raise ValueError('interrupted')
   with execution_lock(path):pass

if __name__=='__main__':unittest.main()
