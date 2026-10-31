"""CPU-only lab maintenance tests. All systemctl, Comfy and GPU calls mocked."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import json
import unittest
import fcntl

P=Path(__file__).resolve().parents[1]/"lab_exclusive.py"
spec=importlib.util.spec_from_file_location("lab_exclusive",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class LabTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"lab"/"autonomous"
        for name in ("pending","running","review_pending"):
            (self.root/name).mkdir(parents=True,exist_ok=True)
        self.active={name:True for name in m.SERVICES}
        self.stops=[]
        self.starts=[]
        self.queues=[True,True,True]
        self.dispatch_count=0
    def ops(self):
        def check_queue():
            return self.queues.pop(0) if self.queues else True
        def stop(name):
            self.stops.append(name)
            self.active[name]=False
        def start(name):
            self.starts.append(name)
            self.active[name]=True
        def dispatch():
            self.dispatch_count+=1
            return SimpleNamespace(returncode=0,stdout='{"status":"GPU_FINISHED_REVIEW_REQUIRED"}')
        return {"is_active":lambda n:self.active[n],"stop":stop,"start":start,
                "queue_empty":check_queue,"pause":lambda _:None,"dispatch":dispatch}
    def pending(self):
        (self.root/"pending/A-00001.json").write_text("{}")
    def test_empty_is_zero_changes(self):
        x=m.run(self.root,Path("/tmp/dummy"),ops=self.ops())
        self.assertEqual(x["status"],"NO_APPROVED_WORK")
        self.assertEqual(self.stops,[])
    def test_review_pending_always_blocks_new_work(self):
        self.pending()
        (self.root/"review_pending/A-00000.json").write_text("{}")
        self.assertEqual(m.run(self.root,Path("/tmp/dummy"),ops=self.ops())["status"],
                         "WAIT_GOLDEN_PIXEL_REVIEW")
    def test_unknown_running_disallows_new_job(self):
        self.pending()
        (self.root/"running/A-00000.json").write_text("{}")
        self.assertEqual(m.run(self.root,Path("/tmp/dummy"),ops=self.ops())["status"],
                         "BLOCKED_UNKNOWN_PREVIOUS_SUBMIT")
    def test_success_quiesces_and_restores(self):
        self.pending()
        x=m.run(self.root,Path("/tmp/dummy"),ops=self.ops())
        self.assertEqual(x["status"],"LAB_SESSION_COMPLETE")
        self.assertEqual(self.dispatch_count,1)
        self.assertEqual(set(self.stops),set(m.SERVICES))
        self.assertEqual(set(self.starts),set(m.SERVICES))
        self.assertFalse((self.root/"service-state.json").exists())
    def test_preexisting_inactive_unit_is_not_started(self):
        self.pending()
        self.active[m.SERVICES[1]]=False
        x=m.run(self.root,Path("/tmp/dummy"),ops=self.ops())
        self.assertEqual(x["status"],"LAB_SESSION_COMPLETE")
        self.assertNotIn(m.SERVICES[1],self.starts)
    def test_busy_queue_does_not_stop_services(self):
        self.pending()
        self.queues=[False]
        x=m.run(self.root,Path("/tmp/dummy"),ops=self.ops())
        self.assertEqual(x["status"],"BLOCKED_COMFY_QUEUE_NOT_EMPTY")
        self.assertEqual(self.stops,[])
        self.assertEqual(self.dispatch_count,0)
    def test_queue_changes_after_quiesce_no_submit(self):
        self.pending()
        self.queues=[True,False]
        x=m.run(self.root,Path("/tmp/dummy"),ops=self.ops())
        self.assertEqual(x["status"],"BLOCKED_UNKNOWN_GPU_OR_QUISCE")
        self.assertEqual(self.dispatch_count,0)
        self.assertTrue((self.root/"service-state.json").exists())
    def test_dispatcher_failure_unknown_preserves_quiesce(self):
        self.pending()
        ops=self.ops()
        ops["dispatch"]=lambda:SimpleNamespace(returncode=1,stdout="")
        x=m.run(self.root,Path("/tmp/dummy"),ops=ops)
        self.assertEqual(x["status"],"BLOCKED_UNKNOWN_GPU_OR_QUISCE")
        self.assertEqual(self.starts,[])
    def test_existing_snapshot_blocks_another_run(self):
        self.pending()
        (self.root/"service-state.json").write_text('{"status":"unknown"}')
        self.assertEqual(m.run(self.root,Path("/tmp/dummy"),ops=self.ops())["status"],
                         "BLOCKED_UNRESOLVED_PRIOR_LAB_SESSION")
    def test_mutual_exclusion(self):
        self.pending()
        path=self.root.parent/"exclusive-dev-lab-maintenance.lock"
        with path.open("a+") as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:
                self.assertEqual(m.run(self.root,Path("/tmp/dummy"),ops=self.ops())["status"],
                                 "LAB_MAINTENANCE_IN_PROGRESS")
            finally:
                fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

if __name__=="__main__":
    unittest.main()
