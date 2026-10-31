"""Negative tests for fenced lease abandonment."""
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("lease_recovery",Path(__file__).resolve().parents[1]/"lease_recovery.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/"state").mkdir()
        with sqlite3.connect(self.root/"state/team.sqlite3") as db:
            db.execute("CREATE TABLE task(id TEXT PRIMARY KEY,state TEXT,owner TEXT,fence TEXT,lease_until REAL,completed_at REAL)")
            db.execute("CREATE TABLE event(seq INTEGER PRIMARY KEY AUTOINCREMENT,ts REAL,task_id TEXT,kind TEXT,detail TEXT)")
            db.execute("INSERT INTO task VALUES ('R-07','leased','owner','fence',2000,NULL)")
    def test_owner_can_quarantine_only_once(self):
        r=m.abandon(self.root,"R-07","owner","fence","real upstream source hook absent",now=1000)
        self.assertTrue(r["abandoned"])
        self.assertFalse(m.abandon(self.root,"R-07","owner","fence","real upstream source hook absent",now=1001)["abandoned"])
        with sqlite3.connect(self.root/"state/team.sqlite3") as db:
            self.assertEqual(db.execute("SELECT state FROM task").fetchone()[0],"blocked")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM event").fetchone()[0],1)
    def test_wrong_owner_or_fence_rejected(self):
        self.assertFalse(m.abandon(self.root,"R-07","other","fence","specific investigation is blocked",now=1000)["abandoned"])
        self.assertFalse(m.abandon(self.root,"R-07","owner","wrong","specific investigation is blocked",now=1000)["abandoned"])
    def test_expired_lease_is_not_abandoned(self):
        self.assertFalse(m.abandon(self.root,"R-07","owner","fence","specific investigation is blocked",now=2001)["abandoned"])
    def test_invalid_reason_rejected(self):
        with self.assertRaises(ValueError):m.abandon(self.root,"R-07","owner","fence","bad",now=1000)
if __name__=="__main__":unittest.main()
