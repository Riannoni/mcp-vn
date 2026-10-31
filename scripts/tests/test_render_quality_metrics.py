"""Synthetic-only offline confusion matrix tests; no private PNGs are read."""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_quality_metrics import summarize_quality


def digest(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def case(index, human, qa):
    png = digest("png-" + str(index))
    return {
        "scene_id": "scene-" + str(index),
        "provenance": {"png_sha256": png},
        "human_label": {"status": human, "reviewed_png_sha256": png},
        "qa": {"status": qa, "png_sha256": png},
    }


def manifest(pairs):
    return {"schema_version": 1,
            "cases": [case(i, h, q) for i, (h, q) in enumerate(pairs)]}


class QualityMetricsTest(unittest.TestCase):
    def test_confusion_matrix_excludes_abstentions_and_unknown_human(self):
        pairs = [
            ("verified", "passed"), ("verified", "passed"),
            ("verified", "rejected"), ("violated", "passed"),
            ("violated", "rejected"), ("violated", "rejected"),
            ("verified", "unobservable"), ("violated", "unknown"),
            ("unknown", "passed"), ("unobservable", "rejected"),
        ]
        report = summarize_quality(manifest(pairs))
        self.assertEqual(report["confusion"], {"tp": 2, "fn": 1, "fp": 1, "tn": 2})
        self.assertEqual(report["human_unknown"], 1)
        self.assertEqual(report["human_unobservable"], 1)
        self.assertEqual(report["qa_unknown_on_labeled"], 1)
        self.assertEqual(report["qa_unobservable_on_labeled"], 1)
        self.assertEqual(report["unsafe_pass_on_unlabeled"], 1)
        self.assertAlmostEqual(report["false_accept_rate"], 1/3)
        self.assertAlmostEqual(report["false_reject_rate"], 1/3)
        self.assertEqual(report["decisive_coverage"], 0.75)
        self.assertFalse(report["release_eligible"])
        self.assertEqual(report["g2_status"], "NOT_INDEPENDENTLY_VERIFIED")

    def test_unknown_only_never_becomes_perfect_accuracy(self):
        doc = manifest([("unknown", "passed"), ("unobservable", "rejected")])
        report = summarize_quality(doc)
        self.assertEqual(report["confusion"], {"tp": 0, "fn": 0, "fp": 0, "tn": 0})
        self.assertIsNone(report["false_accept_rate"])
        self.assertIsNone(report["false_reject_rate"])
        self.assertIsNone(report["decisive_coverage"])
        self.assertEqual(report["unsafe_pass_on_unlabeled"], 1)
        self.assertFalse(report["release_eligible"])

    def test_one_class_does_not_report_zero_error_for_absent_class(self):
        report = summarize_quality(manifest([("verified", "passed")]))
        self.assertIsNone(report["false_accept_rate"])
        self.assertEqual(report["false_reject_rate"], 0.0)
        self.assertFalse(report["release_eligible"])

    def test_explicit_qa_abstention_never_counts_as_false_reject(self):
        report = summarize_quality(manifest([("verified", "unknown"),
                                            ("violated", "unobservable")]))
        self.assertEqual(report["confusion"], {"tp": 0, "fn": 0, "fp": 0, "tn": 0})
        self.assertEqual(report["qa_unknown_on_labeled"], 1)
        self.assertEqual(report["qa_unobservable_on_labeled"], 1)
        self.assertEqual(report["decisive_coverage"], 0.0)

    def test_empty_cases_and_empty_human_label_fail_closed(self):
        with self.assertRaises(ValueError):
            summarize_quality(manifest([]))
        doc = manifest([("verified", "passed")])
        doc["cases"][0]["human_label"]["status"] = ""
        with self.assertRaises(ValueError):
            summarize_quality(doc)
        doc = manifest([("verified", "passed")])
        doc["cases"][0]["human_label"] = {}
        with self.assertRaises(ValueError):
            summarize_quality(doc)

    def test_unknown_status_must_be_explicit_not_missing(self):
        doc = manifest([("verified", "passed")])
        doc["cases"][0]["qa"].pop("status")
        with self.assertRaises(ValueError):
            summarize_quality(doc)

    def test_invalid_enum_and_non_string_status_rejected(self):
        for human, qa in (("yes", "passed"), ("verified", "accepted"),
                          ([], "passed"), ("verified", None)):
            with self.subTest(human=human, qa=qa):
                with self.assertRaises(ValueError):
                    summarize_quality(manifest([(human, qa)]))

    def test_qa_and_human_must_refer_to_exact_png(self):
        for target, key in (("human_label", "reviewed_png_sha256"),
                            ("qa", "png_sha256")):
            doc = manifest([("verified", "passed")])
            doc["cases"][0][target][key] = digest("other")
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    summarize_quality(doc)

    def test_duplicate_scene_or_png_not_independent(self):
        doc = manifest([("verified", "passed"), ("violated", "rejected")])
        doc["cases"][1]["scene_id"] = doc["cases"][0]["scene_id"]
        with self.assertRaises(ValueError):
            summarize_quality(doc)
        doc = manifest([("verified", "passed"), ("violated", "rejected")])
        png = doc["cases"][0]["provenance"]["png_sha256"]
        doc["cases"][1]["provenance"]["png_sha256"] = png
        doc["cases"][1]["human_label"]["reviewed_png_sha256"] = png
        doc["cases"][1]["qa"]["png_sha256"] = png
        with self.assertRaises(ValueError):
            summarize_quality(doc)

    def test_untrusted_metadata_does_not_certify_release(self):
        report = summarize_quality(manifest([("verified", "passed")] * 30))
        self.assertEqual(report["case_count"], 30)
        self.assertFalse(report["release_eligible"])
        self.assertEqual(report["g3_status"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
