import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

MODULE = pathlib.Path(__file__).resolve().parents[1] / "night-mission.py"
sp = importlib.util.spec_from_file_location("nightmission", MODULE)
m = importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)

class MissionTests(unittest.TestCase):
    def test_first_stage(self):
        with tempfile.TemporaryDirectory() as d:
            r = m.next_task(d)
            self.assertEqual(r["stage_id"], "pr49-review")
            self.assertEqual(r["attempt"], 1)
    def test_bounded_retry_moves_on(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.next_task(d)["stage_id"], "pr49-review")
            self.assertEqual(m.next_task(d)["stage_id"], "pr49-review")
            self.assertEqual(m.next_task(d)["stage_id"], "shadow-adapter")
            s=m.read(pathlib.Path(d)/"mission-state.json")
            self.assertEqual(s["history"][0]["status"], "blocked")
    def test_complete_requires_real_test(self):
        with tempfile.TemporaryDirectory() as d:
            m.next_task(d)
            with patch.object(m, "WORK", pathlib.Path(d)):
                m.write(pathlib.Path(d)/"NIGHT_TASK_RESULT_pr49-review.json",
                   {"stage_id":"pr49-review","status":"source_completed"})
                with patch.object(m, "test_evidence", return_value=(True,"passed")):
                    nxt = m.next_task(d)
            self.assertEqual(nxt["stage_id"], "shadow-adapter")
            s=m.read(pathlib.Path(d)/"mission-state.json")
            self.assertEqual(s["history"][0]["status"], "source_completed")
    def test_no_fake_completion_if_tests_fail(self):
        with tempfile.TemporaryDirectory() as d:
            m.next_task(d)
            with patch.object(m, "WORK", pathlib.Path(d)):
                m.write(pathlib.Path(d)/"NIGHT_TASK_RESULT_pr49-review.json",
                   {"stage_id":"pr49-review","status":"source_completed"})
                with patch.object(m,"test_evidence",return_value=(False,"tests_failed")):
                    nxt=m.next_task(d)
            self.assertEqual(nxt["stage_id"],"shadow-adapter")
            s=m.read(pathlib.Path(d)/"mission-state.json")
            self.assertEqual(s["history"][0]["status"],"blocked")
    def test_hyphenated_test_module_executes_real_assertion(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "tests").mkdir()
            (root / "tests" / "atomic-prop-example.test.py").write_text(
                "import unittest\n"
                "class Example(unittest.TestCase):\n"
                " def test_real(self): self.assertEqual(1, 1)\n"
                "if __name__ == '__main__': unittest.main()\n"
            )
            with patch.object(m, "WORK", root):
                self.assertEqual(m.test_evidence("pr49-review"), (True, "passed"))

    def test_hyphenated_failing_assertion_is_not_completed(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "tests").mkdir()
            (root / "tests" / "atomic-prop-example.test.py").write_text(
                "import unittest\n"
                "class Example(unittest.TestCase):\n"
                " def test_fail(self): self.assertEqual(1, 2)\n"
                "if __name__ == '__main__': unittest.main()\n"
            )
            with patch.object(m, "WORK", root):
                self.assertEqual(m.test_evidence("pr49-review"), (False, "tests_failed"))

    def test_zero_discovered_assertions_are_not_completed(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "tests").mkdir()
            (root / "tests" / "atomic-prop-empty.test.py").write_text(
                "import unittest\nif __name__ == '__main__': unittest.main()\n"
            )
            with patch.object(m, "WORK", root):
                self.assertEqual(m.test_evidence("pr49-review"), (False, "tests_failed"))

    def test_missing_matching_files_are_not_completed(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "tests").mkdir()
            with patch.object(m, "WORK", root):
                self.assertEqual(m.test_evidence("pr49-review"), (False, "tests_missing"))

    def test_no_stage_claims_visual_success(self):
        self.assertTrue(all("G2 PASS" not in goal for _,_,goal in m.STAGES))

if __name__=="__main__":
    unittest.main()
