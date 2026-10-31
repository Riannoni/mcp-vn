"""Pure timing audit; no external model or SSH effects."""
import importlib.util
import pathlib
import sqlite3
import unittest

FILE=pathlib.Path(__file__).resolve().parents[1]/"ops/idle_metrics.py"
spec=importlib.util.spec_from_file_location("idle_metrics",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class IdleMetricsTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.row_factory=sqlite3.Row
        self.db.execute("CREATE TABLE task(id TEXT,state TEXT,started_at REAL,completed_at REAL)")
        self.db.execute("CREATE TABLE event(task_id TEXT,kind TEXT,ts REAL)")
        self.addCleanup(self.db.close)

    def add(self,task,state,start=None,end=None,enqueued=10):
        self.db.execute("INSERT INTO task VALUES(?,?,?,?)",(task,state,start,end))
        self.db.execute("INSERT INTO event VALUES(?,'enqueued',?)",(task,enqueued))

    def test_pending_idle_over_10_minutes(self):
        self.add("R-01","done",100,150)
        self.add("R-02","pending",None,None,160)
        x=m.calculate(self.db,now=780)["R"]
        self.assertEqual(x["state"],"pending_ready_or_dependency")
        self.assertEqual(x["ready_idle_seconds"],620)
        self.assertEqual(x["worker_idle_seconds"],630)
        self.assertTrue(x["over_10_minutes"])

    def test_active_worker_has_no_idle_alert(self):
        self.add("R-01","done",100,150)
        self.add("R-02","leased",300,None,151)
        x=m.calculate(self.db,now=10000)["R"]
        self.assertEqual(x["state"],"working")
        self.assertIsNone(x["ready_idle_seconds"])
        self.assertFalse(x["over_10_minutes"])

    def test_review_pending_has_no_false_actionable_sla(self):
        self.add("R-01","done",100,150)
        self.add("R-02","review_pending",300,340,151)
        x=m.calculate(self.db,now=10000)["R"]
        self.assertEqual(x["state"],"awaiting_independent_review")
        self.assertFalse(x["over_10_minutes"])

    def test_historical_gap_percentiles(self):
        self.add("R-01","done",100,150)
        self.add("R-02","done",190,220,155)
        self.add("R-03","done",320,350,221)
        x=m.calculate(self.db,now=400)["R"]
        self.assertEqual(x["historical_gaps"],2)
        self.assertEqual(x["gap_p50_seconds"],70)
        self.assertEqual(x["gap_p90_seconds"],94)

    def test_no_backlog_excluded(self):
        self.add("R-01","done",100,150)
        x=m.calculate(self.db,now=100000)["R"]
        self.assertFalse(x["over_10_minutes"])
        self.assertIsNone(x["ready_idle_seconds"])


if __name__=="__main__":
    unittest.main()
