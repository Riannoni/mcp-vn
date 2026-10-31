"""Isolated wake guard regression tests; no ChatGPT, network or GPU used."""
import importlib.util
import json
import pathlib
import sqlite3
import subprocess
import tempfile
import unittest

FILE=pathlib.Path(__file__).resolve().parents[1]/"ops/wake_guard.py"
spec=importlib.util.spec_from_file_location("wakeguard",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class WakeGuardTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=pathlib.Path(t.name)
        (self.root/"state").mkdir()
        w=self.root/"lane-renderer"
        w.mkdir()
        subprocess.run(["git","init","-q",str(w)],check=True)
        subprocess.run(["git","-C",str(w),"config","user.name","test"],check=True)
        subprocess.run(["git","-C",str(w),"config","user.email","test@example.invalid"],check=True)
        (w/"AGENTS.md").write_text("source")
        subprocess.run(["git","-C",str(w),"add","."],check=True)
        subprocess.run(["git","-C",str(w),"commit","-qm","base"],check=True)
        db=sqlite3.connect(self.root/"state/team.sqlite3")
        db.execute("CREATE TABLE team_meta(k TEXT PRIMARY KEY,v TEXT)")
        db.execute("INSERT INTO team_meta VALUES('state','active')")
        db.execute("CREATE TABLE task(id TEXT PRIMARY KEY,state TEXT, deps TEXT,paths TEXT,priority INTEGER)")
        db.execute("INSERT INTO task VALUES('R-03','pending','[]','[\"worker/x.py\"]',10)")
        db.commit()
        db.close()

    def db(self):
        return sqlite3.connect(self.root/"state/team.sqlite3")

    def set_task(self,task_id,state):
        db=self.db()
        db.execute("UPDATE task SET state=? WHERE id=?",(state,task_id))
        db.commit();db.close()

    def test_ready_without_mutating_db(self):
        self.assertTrue(m.check(self.root,"R",now=100)["eligible"])
        db=self.db()
        self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='wake_reservation'").fetchone())
        db.close()

    def test_reservation_atomic_and_cooldown(self):
        first=m.check(self.root,"R",reserve=True,now=100)
        self.assertTrue(first["reserved"])
        second=m.check(self.root,"R",reserve=True,now=101)
        self.assertFalse(second["eligible"])
        self.assertEqual(second["reason"],"wake_cooldown")
        later=m.check(self.root,"R",now=3701)
        self.assertTrue(later["eligible"])

    def test_review_pending_or_blocker_prevents_wake(self):
        for state,expected in [("leased","worker_busy"),("review_pending","review_pending"),("blocked","blocker_requires_review")]:
            self.set_task("R-03",state)
            result=m.check(self.root,"R",now=100)
            self.assertEqual(result["reason"],expected)

    def test_dependencies_checked(self):
        db=self.db()
        db.execute("UPDATE task SET deps='[\"R-02\"]' WHERE id='R-03'")
        db.commit();db.close()
        self.assertEqual(m.check(self.root,"R",now=100)["reason"],"no_ready_task")
        db=self.db()
        db.execute("INSERT INTO task VALUES('R-02','done','[]','[\"worker/y.py\"]',1)")
        db.commit();db.close()
        self.assertTrue(m.check(self.root,"R",now=100)["eligible"])

    def test_worktree_dirty_rejected(self):
        (self.root/"lane-renderer/untracked").write_text("changed")
        self.assertEqual(m.check(self.root,"R",now=100)["reason"],"worktree_dirty_or_missing")

    def test_stopped_team_rejected(self):
        db=self.db();db.execute("UPDATE team_meta SET v='stopped'");db.commit();db.close()
        self.assertEqual(m.check(self.root,"R",now=100)["reason"],"team_inactive")

    def test_cross_lane_conflict_prevents_wake(self):
        db=self.db()
        db.execute("INSERT INTO task VALUES('Q-01','leased','[]','[\"worker/x.py\"]',3)")
        db.commit();db.close()
        self.assertEqual(m.check(self.root,"R",now=100)["reason"],"no_ready_task")

    def test_unrelated_lane_lease_allows_wake(self):
        db=self.db()
        db.execute("INSERT INTO task VALUES('Q-01','leased','[]','[\"tests/other.py\"]',3)")
        db.commit();db.close()
        self.assertTrue(m.check(self.root,"R",now=100)["eligible"])


if __name__=="__main__":
    unittest.main()
