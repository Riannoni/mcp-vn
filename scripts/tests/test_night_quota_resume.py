import importlib.util
import pathlib
import unittest

SRC = pathlib.Path(__file__).resolve().parents[1] / "night-quota-resume.py"
s = importlib.util.spec_from_file_location("night_resume", SRC)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.meta={"run_id":"20261031-021227","deadline_epoch":500}
        self.status={"state":"paused_quota","last_outcome":"5h_or_primary used >= 85%"}
    def test_short_window_resumes(self):
        self.assertEqual(m.can_resume(self.meta,self.status,False,200),(True,"eligible"))
    def test_long_window_no_resume(self):
        self.status["last_outcome"]="7d_or_secondary used >= 85%"
        self.assertEqual(m.can_resume(self.meta,self.status,False,200)[0],False)
    def test_failing_not_restarted(self):
        self.status["state"]="blocked_repeated_error"
        self.assertFalse(m.can_resume(self.meta,self.status,False,200)[0])
    def test_active_not_restarted(self):
        self.assertFalse(m.can_resume(self.meta,self.status,True,200)[0])
    def test_deadline_never_extended(self):
        self.assertFalse(m.can_resume(self.meta,self.status,False,500)[0])
if __name__=="__main__":
    unittest.main()
