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

    def test_serial_lane_claims_keep_shared_worktree_submissions_in_scope(self):
        first=m.claim(self.db,"R","first-author")
        self.assertEqual(first["id"],"R-01")
        # Both scopes are disjoint and the worktree is still clean. A second
        # claim here would bind both tasks to the same pre-change Git baseline.
        self.assertFalse(m.claim(self.db,"R","second-author")["claimed"])
        work=self.root/"lane-renderer"
        evidence_dir=self.root/"evidence/renderer"
        evidence_dir.mkdir(parents=True)

        def commit_and_submit(task,owner,relative_path):
            source=work/relative_path
            source.parent.mkdir(parents=True,exist_ok=True)
            source.write_text("VERSION = 1\n")
            git(work,"add",relative_path)
            git(work,"commit","-qm",task["id"])
            evidence=evidence_dir/(task["id"]+".json")
            evidence.write_text(json.dumps({
                "source_status":"tested_isolated","g2":"UNVERIFIED",
                "g3":"NO_GO","tests":["isolated source fixture"],
                "changed_paths":[relative_path]}))
            return m.submit(self.db,"R",owner,task["fence"],task["id"],evidence)

        first_result=commit_and_submit(first,"first-author","worker/bimanual_scene_planner.py")
        self.assertTrue(first_result["accepted"])
        second=m.claim(self.db,"R","second-author")
        self.assertEqual(second["id"],"R-02")
        baseline=self.db.execute(
            "SELECT head FROM claim_baselines WHERE task_id='R-02'"
        ).fetchone()[0]
        self.assertEqual(baseline,first_result["commit_sha"])
        self.assertTrue(commit_and_submit(
            second,"second-author","worker/prop_layer_compositor.py"
        )["accepted"])

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
        commit=git(work, "rev-parse", "HEAD")
        with self.assertRaises(ValueError):
            m.review(self.db, "R-01", True, "Independent source diff and test replay OK")
        self.assertTrue(m.review(self.db, "R-01", True, "Independent source diff and test replay OK", commit)["approved"])
        self.assertEqual(self.db.execute("SELECT state FROM task WHERE id='R-01'").fetchone()["state"], "done")

    def test_uncommitted_source_never_submitted(self):
        task = m.claim(self.db, "R", "writer")
        work = self.root / "lane-renderer"
        path = work / "worker/bimanual_scene_planner.py"
        path.parent.mkdir(parents=True)
        path.write_text("UNCOMMITTED = 1\n")
        e = self.root / "evidence/renderer/uncommitted.json"
        e.parent.mkdir(parents=True, exist_ok=True)
        e.write_text(json.dumps({
            "source_status":"tested_isolated", "g2":"UNVERIFIED",
            "g3":"NO_GO", "tests":["red/green 1"], "summary":"pending",
            "changed_paths":["worker/bimanual_scene_planner.py"]}))
        with self.assertRaisesRegex(ValueError,"uncommitted"):
            m.submit(self.db,"R","writer",task["fence"],task["id"],e)
        self.assertEqual(self.db.execute("SELECT state FROM task WHERE id='R-01'").fetchone()["state"],"leased")

    def test_committed_scope_and_moving_head_are_distinct(self):
        first=m.claim(self.db, "R", "author")
        work=self.root/"lane-renderer"
        a=work/"worker/bimanual_scene_planner.py"
        a.parent.mkdir(parents=True)
        a.write_text("VERSION = 1\n")
        git(work,"add",a.relative_to(work).as_posix())
        git(work,"commit","-qm","one")
        first_sha=git(work,"rev-parse","HEAD")
        evidence=self.root/"evidence/renderer/proof1.json"
        evidence.parent.mkdir(parents=True,exist_ok=True)
        evidence.write_text(json.dumps({"source_status":"tested_isolated",
            "g2":"UNVERIFIED","g3":"NO_GO","tests":["1/1"],
            "summary":"One checked commit","changed_paths":["worker/bimanual_scene_planner.py"]}))
        self.assertTrue(m.submit(self.db,"R","author",first["fence"],first["id"],evidence)["accepted"])
        b=work/"tests/bimanual-scene-planner.test.py"
        b.parent.mkdir(parents=True)
        b.write_text("def test_new(): assert True\n")
        git(work,"add",b.relative_to(work).as_posix())
        git(work,"commit","-qm","later commit")
        with self.assertRaisesRegex(ValueError,"exact submitted commit"):
            m.review(self.db,"R-01",True,"Reviewed later code incorrectly",git(work,"rev-parse","HEAD"))
        self.assertTrue(m.review(self.db,"R-01",True,"Independent test run on first commit",first_sha)["approved"])

    def test_out_of_scope_commit_rejected(self):
        task=m.claim(self.db,"R","author")
        work=self.root/"lane-renderer"
        f=work/"docs/unapproved.md"
        f.write_text("unapproved\n")
        git(work,"add","docs/unapproved.md")
        git(work,"commit","-qm","bad")
        evidence=self.root/"evidence/renderer/bad.json"
        evidence.parent.mkdir(parents=True,exist_ok=True)
        evidence.write_text(json.dumps({"source_status":"tested_isolated",
            "g2":"UNVERIFIED","g3":"NO_GO","tests":["fake"],
            "changed_paths":["worker/bimanual_scene_planner.py"]}))
        with self.assertRaisesRegex(ValueError,"out-of-scope"):
            m.submit(self.db,"R","author",task["fence"],task["id"],evidence)

    def test_existing_symlink_escape_rejects_claim(self):
        w=self.root/"lane-renderer"
        p=w/"worker"
        p.symlink_to(self.root, target_is_directory=True)
        git(w,"add","worker")
        git(w,"commit","-qm","symlink fixture")
        with self.assertRaisesRegex(ValueError,"escapes lane"):
            m.claim(self.db,"R","author")

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

    def test_reboot_fences_leased_worker_before_original_timeout(self):
        import time
        task=m.claim(self.db,"R","worker-before-power-outage")
        self.assertTrue(task["claimed"])
        self.db.execute("UPDATE task SET lease_until=? WHERE id='R-01'",(time.time()+3600,))
        m.watchdog(self.db,observed_boot_id="boot-A")
        self.assertEqual(self.db.execute("SELECT state FROM task WHERE id='R-01'").fetchone()["state"],"leased")
        m.watchdog(self.db,observed_boot_id="boot-B")
        x=self.db.execute("SELECT state,owner,fence FROM task WHERE id='R-01'").fetchone()
        self.assertEqual(x["state"],"blocked")
        self.assertIsNone(x["owner"])
        self.assertIsNone(x["fence"])
        with self.assertRaisesRegex(RuntimeError,"host reboot detected"):
            m.claim(self.db,"R","second")

    def test_independent_lane_work_ignores_unrelated_blocked_scope(self):
        self.db.execute("UPDATE task SET state='blocked' WHERE id='R-01'")
        answer=m.claim(self.db,"R","new-owner")
        self.assertTrue(answer["claimed"])
        self.assertEqual(answer["id"],"R-02")

    def test_conflicting_blocked_scope_is_still_fenced(self):
        self.db.execute("UPDATE task SET state='blocked',paths=? WHERE id='R-01'",('["worker/bimanual_scene_planner.py"]',))
        self.db.execute("UPDATE task SET paths=? WHERE id='R-02'",('["worker/bimanual_scene_planner.py"]',))
        answer=m.claim(self.db,"R","new-owner")
        self.assertFalse(answer["claimed"])

    def test_no_reboot_does_not_fence_live_lease(self):
        import time
        m.claim(self.db,"R","worker")
        self.db.execute("UPDATE task SET lease_until=? WHERE id='R-01'",(time.time()+3600,))
        m.watchdog(self.db,observed_boot_id="same-boot")
        m.watchdog(self.db,observed_boot_id="same-boot")
        self.assertEqual(self.db.execute("SELECT state FROM task WHERE id='R-01'").fetchone()["state"],"leased")

    def test_old_worker_submit_rejected_before_boot_reconciliation(self):
        m.claim(self.db,"R","old-lease")
        m.watchdog(self.db,observed_boot_id="synthetic-old-boot")
        with self.assertRaisesRegex(RuntimeError,"host reboot detected"):
            m.submit(self.db,"R","old-lease","bogus","R-01","missing-evidence.json")

    def test_watchdog_emits_only_on_state_change(self):
        before=self.db.execute("SELECT COUNT(*) FROM event").fetchone()[0]
        first=m.watchdog(self.db)
        n1=self.db.execute("SELECT COUNT(*) FROM event").fetchone()[0]
        self.assertEqual(n1,before+2)
        second=m.watchdog(self.db)
        n2=self.db.execute("SELECT COUNT(*) FROM event").fetchone()[0]
        self.assertEqual(n2,n1)
        self.assertEqual(first["warnings"],second["warnings"])
        m.claim(self.db,"R","writer")
        m.watchdog(self.db)
        self.assertGreater(self.db.execute("SELECT COUNT(*) FROM event").fetchone()[0],n2+1)

    def test_submit_no_git_symlink_in_output(self):
        task=m.claim(self.db,"R","writer")
        w=self.root/"lane-renderer"
        dest=w/"worker/bimanual_scene_planner.py"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(self.root/"AGENTS.md")
        git(w,"add","worker/bimanual_scene_planner.py")
        git(w,"commit","-qm","bad symlink output")
        evidence=self.root/"evidence/renderer/symlink.json"
        evidence.parent.mkdir(parents=True,exist_ok=True)
        evidence.write_text(json.dumps({"source_status":"tested_isolated",
            "g2":"UNVERIFIED","g3":"NO_GO","tests":["syntax"],
            "changed_paths":["worker/bimanual_scene_planner.py"]}))
        with self.assertRaisesRegex(ValueError,"symlink|escapes"):
            m.submit(self.db,"R","writer",task["fence"],task["id"],evidence)

    def test_stop_disables_claims(self):
        self.db.execute("UPDATE team_meta SET v='stopped' WHERE k='state'")
        x = m.claim(self.db, "R", "owner")
        self.assertEqual(x["reason"], "paused")


if __name__ == "__main__":
    unittest.main()
