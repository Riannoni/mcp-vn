"""Offline negative regression tests; no browser, model or user images."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "golden-label-eval.py"
spec = importlib.util.spec_from_file_location("golden_label_eval", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sample(i=1, human="verified", qa="verified", decision="accept"):
    c = format(i, "064x")
    return {
        "scene_id": f"independent-scene-{i}", "first_attempt": True,
        "source_state_sha256": "a" * 64, "candidate_sha256": c,
        "mandatory": ["props", "contact"],
        "human": {"independent": True, "candidate_sha256": c,
                  "verdicts": {"props": human, "contact": human}},
        "qa": {"candidate_sha256": c, "decision": decision,
               "verdicts": {"props": qa, "contact": qa}},
    }


class GoldenLabelEvalTests(unittest.TestCase):
    def test_positive_is_source_only_not_release(self):
        result = mod.evaluate([sample()])
        self.assertEqual(result["human_accepted"], 1)
        self.assertEqual(result["release_status"], "NO_GO_SOURCE_ONLY")

    def test_grounded_false_accept(self):
        result = mod.evaluate([sample(human="violated")])
        self.assertEqual(result["false_accept"], 1)

    def test_unobservable_human_is_not_negative_ground_truth(self):
        result = mod.evaluate([sample(human="unobservable")])
        self.assertEqual(result["human_unresolved"], 1)
        self.assertEqual(result["false_accept"], 0)
        self.assertEqual(result["unresolved_accepted"], 1)

    def test_unobservable_qa_accept_is_unsafe(self):
        result = mod.evaluate([sample(qa="unobservable")])
        self.assertEqual(result["unsafe_accept"], 1)

    def test_false_reject(self):
        result = mod.evaluate([sample(decision="reject")])
        self.assertEqual(result["false_reject"], 1)

    def test_cross_candidate_qa_rejected(self):
        row = sample()
        row["qa"]["candidate_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "cross-candidate"):
            mod.evaluate([row])

    def test_cross_candidate_human_rejected(self):
        row = sample()
        row["human"]["candidate_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "cross-candidate"):
            mod.evaluate([row])

    def test_missing_mandatory_observation_rejected(self):
        row = sample()
        del row["qa"]["verdicts"]["contact"]
        with self.assertRaisesRegex(ValueError, "missing/invalid"):
            mod.evaluate([row])

    def test_unhashable_qa_verdict_fails_closed(self):
        row = sample()
        row["qa"]["verdicts"]["contact"] = {"unexpected": True}
        with self.assertRaisesRegex(ValueError, "missing/invalid"):
            mod.evaluate([row])

    def test_mandatory_not_applicable_rejected(self):
        row = sample(qa="not_applicable")
        with self.assertRaisesRegex(ValueError, "mandatory verdict"):
            mod.evaluate([row])

    def test_duplicate_scene_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mod.evaluate([sample(), sample()])

    def test_claimed_independence_must_be_explicit(self):
        row = sample()
        row["human"]["independent"] = False
        with self.assertRaisesRegex(ValueError, "independent"):
            mod.evaluate([row])

    def test_invalid_hash_rejected(self):
        row = sample()
        row["candidate_sha256"] = "0" * 63
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            mod.evaluate([row])

    def test_first_attempt_boolean_required(self):
        row = sample()
        row["first_attempt"] = 1
        with self.assertRaisesRegex(ValueError, "boolean"):
            mod.evaluate([row])

    def test_30_ids_do_not_certify_visual_evidence(self):
        result = mod.evaluate([sample(i) for i in range(1, 31)])
        self.assertTrue(result["minimum_30_scene_ids_present"])
        self.assertEqual(result["release_status"], "NO_GO_SOURCE_ONLY")

    def test_cli_rejects_invalid_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"samples": [sample(), sample()]}))
            run = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 2)
            self.assertIn("INVALID_DATASET", run.stderr)


if __name__ == "__main__":
    unittest.main()
