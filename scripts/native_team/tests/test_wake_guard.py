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
# Quota admission has an independent, focused test suite; this fixture tests wake CAS.
m.quota_permit=lambda root,now,provider="codex_oauth": {"eligible":True}


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
        db.execute("CREATE TABLE task(id TEXT PRIMARY KEY,state TEXT, deps TEXT,paths TEXT,priority INTEGER,completed_at REAL)")
        db.execute("INSERT INTO task(id,state,deps,paths,priority) VALUES('R-03','pending','[]','[\"worker/x.py\"]',10)")
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

    def test_concurrent_wake_reservations_accept_one(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            attempts=list(pool.map(
                lambda _:m.check(self.root,"R",reserve=True,now=100),
                range(4)))
        self.assertEqual(sum(bool(a.get("reserved")) for a in attempts),1)
        self.assertEqual(sum(a.get("reason")=="wake_cooldown" for a in attempts),3)

    def test_hourly_lane_budget_prevents_wake_storm(self):
        first=m.check(self.root,"R",reserve=True,now=100)
        self.assertTrue(first["reserved"])
        db=self.db()
        db.execute("UPDATE wake_reservation SET requested_at=-10000 WHERE lane='R'")
        db.commit();db.close()
        # 6 explicit wake reservations in one hour must cap further requests.
        db=self.db()
        for i in range(5):
            db.execute("INSERT INTO wake_history(lane,requested_at,task_id,requestor) VALUES('R',?,?,?)",(150+i,'R-03','test'))
        db.commit();db.close()
        second=m.check(self.root,"R",reserve=True,now=701)
        self.assertFalse(second["eligible"])
        self.assertEqual(second["reason"],"lane_hourly_wake_budget")
        self.assertTrue(m.check(self.root,"R",now=4402)["eligible"])

    def test_chief_hourly_budget(self):
        db=self.db()
        db.execute("UPDATE task SET state='review_pending',completed_at=100")
        db.commit();db.close()
        self.assertTrue(m.check_review(self.root,reserve=True,now=100)["reserved"])
        db=self.db()
        db.execute("UPDATE wake_reservation SET requested_at=-10000 WHERE lane='C'")
        db.commit();db.close()
        db=self.db()
        for i in range(11):
            db.execute("INSERT INTO wake_history(lane,requested_at,task_id,requestor) VALUES('C',?,?,?)",(151+i,'R-03','test'))
        db.commit();db.close()
        second=m.check_review(self.root,reserve=True,now=701)
        self.assertEqual(second["reason"],"chief_hourly_wake_budget")

    def test_review_pending_or_blocker_prevents_wake(self):
        for state,expected in [("leased","worker_busy"),("review_pending","review_pending"),("blocked","blocker_requires_review")]:
            self.set_task("R-03",state)
            result=m.check(self.root,"R",now=100)
            self.assertEqual(result["reason"],expected)

    def test_unrelated_blocked_scope_does_not_stop_lane(self):
        self.set_task("R-03","blocked")
        db=self.db()
        db.execute("INSERT INTO task(id,state,deps,paths,priority) VALUES(\'R-04\',\'pending\',\'[]\',\'[\"worker/y.py\"]\',5)")
        db.commit();db.close()
        self.assertTrue(m.check(self.root,"R",now=100)["eligible"])

    def test_dependencies_checked(self):
        db=self.db()
        db.execute("UPDATE task SET deps='[\"R-02\"]' WHERE id='R-03'")
        db.commit();db.close()
        self.assertEqual(m.check(self.root,"R",now=100)["reason"],"no_ready_task")
        db=self.db()
        db.execute("INSERT INTO task(id,state,deps,paths,priority) VALUES('R-02','done','[]','[\"worker/y.py\"]',1)")
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
        db.execute("INSERT INTO task(id,state,deps,paths,priority) VALUES('Q-01','leased','[]','[\"worker/x.py\"]',3)")
        db.commit();db.close()
        self.assertEqual(m.check(self.root,"R",now=100)["reason"],"no_ready_task")

    def test_chief_review_ready_and_reservation(self):
        db=self.db()
        db.execute("UPDATE task SET state='review_pending',completed_at=100 WHERE id='R-03'")
        db.commit();db.close()
        r=m.check_review(self.root,now=200)
        self.assertTrue(r["eligible"])
        self.assertEqual(r["review_count"],1)
        first=m.check_review(self.root,reserve=True,now=200,requestor="R-worker")
        self.assertTrue(first.get("reserved"))
        next_=m.check_review(self.root,reserve=True,now=201,requestor="Q-worker")
        self.assertEqual(next_["reason"],"chief_wake_cooldown")
        self.assertTrue(m.check_review(self.root,now=3801)["eligible"])

    def test_chief_review_waits_briefly_on_live_workers(self):
        db=self.db()
        db.execute("UPDATE task SET state='review_pending',completed_at=100 WHERE id='R-03'")
        db.execute("INSERT INTO task(id,state,deps,paths,priority,completed_at) VALUES('Q-01','leased','[]','[]',1,NULL)")
        db.commit();db.close()
        r=m.check_review(self.root,now=150)
        self.assertEqual(r["reason"],"other_workers_finishing")
        self.assertTrue(m.check_review(self.root,now=250)["eligible"])

    def test_chief_review_requires_pending_and_active_team(self):
        self.assertEqual(m.check_review(self.root,now=100)["reason"],"nothing_to_review")
        db=self.db()
        db.execute("UPDATE task SET state='review_pending',completed_at=50")
        db.execute("UPDATE team_meta SET v='stopped'")
        db.commit();db.close()
        self.assertEqual(m.check_review(self.root,now=100)["reason"],"team_inactive")

    def test_chief_review_concurrent_one_reservation(self):
        from concurrent.futures import ThreadPoolExecutor
        db=self.db()
        db.execute("UPDATE task SET state='review_pending',completed_at=100")
        db.commit();db.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:m.check_review(
                self.root,reserve=True,now=300,requestor="worker"),range(4)))
        self.assertEqual(sum(bool(x.get("reserved")) for x in results),1)

    def test_unrelated_lane_lease_allows_wake(self):
        db=self.db()
        db.execute("INSERT INTO task(id,state,deps,paths,priority) VALUES('Q-01','leased','[]','[\"tests/other.py\"]',3)")
        db.commit();db.close()
        self.assertTrue(m.check(self.root,"R",now=100)["eligible"])


if __name__=="__main__":
    unittest.main()
