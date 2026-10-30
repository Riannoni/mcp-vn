import importlib.util
import pathlib
import unittest
sp=importlib.util.spec_from_file_location("watchdog",pathlib.Path(__file__).resolve().parents[1]/"night-watchdog.py")
mod=importlib.util.module_from_spec(sp)
sp.loader.exec_module(mod)

class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.m={"deadline_epoch":2000}
        self.s={"state":"working","updated_at":"1970-01-01T00:16:30+00:00"}
    def c(self, active=False, now=1000, recovery=None):
        return mod.classify(self.m,self.s,active,now,recovery or {})
    def test_healthy(self):
        self.assertEqual(self.c(True),"healthy")
    def test_dead_restarts_bounded(self):
        self.assertEqual(self.c(False),"safe_to_restart")
        self.assertEqual(self.c(False,recovery={"restart_count":2}),"restart_budget_exhausted")
    def test_cooldown(self):
        self.assertEqual(self.c(False,recovery={"restart_count":1,"last_restart_epoch":990}),"restart_cooldown")
    def test_stale_does_not_kill_live(self):
        self.s["updated_at"]="1970-01-01T00:00:00+00:00"
        self.assertEqual(self.c(True),"stale_running")
    def test_no_resume_quota_or_human(self):
        for state in ("paused_quota","blocked_human_gate","stopped","completed_time_limit"):
            self.s["state"]=state
            self.assertEqual(self.c(),"not_recoverable")
    def test_no_resume_failed_codex(self):
        self.s["state"]="blocked_repeated_error"
        self.assertEqual(self.c(),"needs_diagnosis")
    def test_deadline(self):
        self.assertEqual(self.c(False,now=2000),"finished")
if __name__=="__main__":unittest.main()
