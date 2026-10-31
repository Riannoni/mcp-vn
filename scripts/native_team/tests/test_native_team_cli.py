"""Fail-closed integration checks for local four-lane native-team control CLI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))
spec = importlib.util.spec_from_file_location("native_team_cli", SRC / "teamctl.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def git(worktree, *args):
    p = subprocess.run(["git", *args], cwd=worktree, text=True,
                       capture_output=True, check=True, timeout=12)
    return p.stdout.strip()


class FourLaneControlTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name) / "team"
        self.root.mkdir()
        self.saved_root, self.saved_db = m.ROOT, m.DB
        self.addCleanup(self.restore_globals)
        m.ROOT = self.root
        m.DB = self.root / "state" / "team.sqlite3"
        for lane in m.LANES.values():
            w = self.root / ("lane-" + lane)
            w.mkdir()
            git(w, "init", "-q")
            git(w, "config", "user.name", "Native Team Test")
            git(w, "config", "user.email", "native-team@example.invalid")
            (w / "docs").mkdir()
            (w / "AGENTS.md").write_text("Required rules\n")
            (w / "docs/DEVELOPMENT-AND-TESTING.md").write_text("Full rules\n")
            git(w, "add", "-A")
            git(w, "commit", "-qm", "fixture")
        self.assertEqual(m.initialize()["tasks"], 8)
        self.db = m.open_db()
        self.addCleanup(self.db.close)

    def restore_globals(self):
        m.ROOT, m.DB = self.saved_root, self.saved_db

    def test_four_unique_lanes_and_single_lease(self):
        claims = {x: m.claim(self.db, x, "test-" + x) for x in m.LANES}
        self.assertTrue(all(x["claimed"] for x in claims.values()))
        self.assertEqual(len({x["fence"] for x in claims.values()}), 4)
        self.assertFalse(m.claim(self.db, "R", "duplicate")["claimed"])

    def test_submission_requires_review_before_done(self):
        task = m.claim(self.db, "R", "old")
        self.assertTrue(task["claimed"])
        work = self.root / "lane-renderer"
        file = work / "worker/bimanual_scene_planner.py"
        file.parent.mkdir(parents=True)
        file.write_text("PLAN_VERSION = 1\n")
        git(work, "add", file.relative_to(work).as_posix())
        git(work, "commit", "-qm", "test source change")
        path = self.root / "evidence/renderer/proof.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "source_status": "tested_isolated", "g2": "UNVERIFIED",
            "g3": "NO_GO", "tests": ["negative red then green, 1/1"],
            "changed_paths": ["worker/bimanual_scene_planner.py"],
            "summary": "correct bounded source test"
        }))
        self.assertTrue(m.submit(self.db, "R", "old", task["fence"], task["id"], path)["accepted"])
        self.assertEqual(self.db.execute("SELECT state FROM task WHERE id='R-01'").fetchone()["state"], "review_pending")
        self.assertTrue(m.review(self.db, "R-01", True, "Independent source diff and test replay OK")["approved"])
        self.assertEqual(self.db.execute("SELECT state FROM task WHERE id='R-01'").fetchone()["state"], "done")

    def test_forged_visual_pass_is_rejected(self):
        task = m.claim(self.db, "R", "old")
        path = self.root / "evidence/renderer/proof.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"source_status": "tested_isolated", "g2": "PASS", "g3": "NO_GO",
                                    "tests": ["fake"], "changed_paths": ["worker/bimanual_scene_planner.py"]}))
        with self.assertRaises(ValueError):
            m.submit(self.db, "R", "old", task["fence"], task["id"], path)

    def test_stale_lease_blocks_reclaim(self):
        m.claim(self.db, "R", "old")
        self.db.execute("UPDATE task SET lease_until=0 WHERE id='R-01'")
        m.watchdog(self.db)
        self.assertEqual(self.db.execute("SELECT state FROM task WHERE id='R-01'").fetchone()["state"], "blocked")
        x = m.claim(self.db, "R", "new")
        self.assertTrue(x["claimed"])
        self.assertEqual(x["id"], "R-02")

    def test_dirty_worktree_cannot_start_another_task(self):
        w = self.root / "lane-renderer"
        (w / "untracked.py").write_text("unsafe")
        x = m.claim(self.db, "R", "owner")
        self.assertEqual(x["reason"], "dirty_worktree_needs_review")

    def test_stop_disables_claims(self):
        self.db.execute("UPDATE team_meta SET v='stopped' WHERE k='state'")
        x = m.claim(self.db, "R", "owner")
        self.assertEqual(x["reason"], "paused")


if __name__ == "__main__":
    unittest.main()
