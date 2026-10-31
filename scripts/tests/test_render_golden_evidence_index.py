"""Offline tests: fixture pixels are synthetic, never release evidence."""
import copy
import hashlib
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_golden_evidence_index import audit_evidence
from test_render_golden_set_audit import example_case


def png_bytes(rgb):
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload +
                struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(b"\x00" + bytes(rgb))) +
            chunk(b"IEND", b""))


class EvidenceIndexTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def case(self, index, *, origin="real_comfy_job",
             review="independent_human", status="verified", qa="passed"):
        c = example_case(index)
        raw = png_bytes((index % 256, (index // 256) % 256, 33))
        png = hashlib.sha256(raw).hexdigest()
        (self.root / f"image-{index}.png").write_bytes(raw)
        c["provenance"]["png_sha256"] = png
        c["named_actors"][0]["evidence"]["png_sha256"] = png
        c["required_objects"][0]["evidence"]["png_sha256"] = png
        c["human_label"].update({
            "reviewed_png_sha256": png, "status": status,
            "reviewer_type": "human", "review_source": review,
            "reviewed_at": "2026-10-31T06:00:00Z",
        })
        c["qa"] = {"status": qa, "png_sha256": png}
        receipt = {
            "capture_kind": origin,
            "captured_at": "2026-10-31T05:00:00Z",
            "scene_id": c["scene_id"],
            "source_sha256": c["source_sha256"],
            "reference_sha256": c["reference_sha256"],
            "provenance": dict(c["provenance"]),
        }
        receipt_raw = json.dumps(receipt, sort_keys=True).encode()
        (self.root / f"receipt-{index}.json").write_bytes(receipt_raw)
        c["artifact"] = {
            "png_path": f"image-{index}.png",
            "receipt_path": f"receipt-{index}.json",
            "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        }
        return c

    def run_index(self, cases, latency=None):
        doc = {"schema_version": 1, "cases": cases}
        if latency is not None:
            doc["latency_observations"] = latency
        return audit_evidence(doc, self.root)

    def test_red_thirty_synthetic_never_qualify(self):
        cases = [self.case(i, origin="synthetic") for i in range(30)]
        result = self.run_index(cases)
        self.assertEqual(result["human_attested_real_cases"], 0)
        self.assertFalse(result["coverage"]["meets_30"])
        self.assertFalse(result["release_eligible"])

    def test_red_thirty_self_labels_never_qualify(self):
        cases = [self.case(i, review="self_label") for i in range(30)]
        result = self.run_index(cases)
        self.assertEqual(result["human_attested_real_cases"], 0)
        self.assertFalse(result["release_eligible"])

    def test_red_reused_real_frame_never_qualifies_as_thirty(self):
        cases = [self.case(i) for i in range(30)]
        for i in range(1, 30):
            cases[i]["provenance"]["png_sha256"] = cases[0]["provenance"]["png_sha256"]
            cases[i]["artifact"]["png_path"] = cases[0]["artifact"]["png_path"]
            cases[i]["human_label"]["reviewed_png_sha256"] = cases[0]["provenance"]["png_sha256"]
            cases[i]["qa"]["png_sha256"] = cases[0]["provenance"]["png_sha256"]
        result = self.run_index(cases)
        self.assertLess(result["human_attested_real_cases"], 30)
        self.assertFalse(result["coverage"]["meets_30"])

    def test_thirty_attested_real_files_are_not_release_certified(self):
        result = self.run_index([self.case(i) for i in range(30)])
        self.assertEqual(result["verified_png_files"], 30)
        self.assertEqual(result["human_attested_real_cases"], 30)
        self.assertTrue(result["coverage"]["meets_30"])
        self.assertFalse(result["release_eligible"])
        self.assertEqual(result["g2_status"], "UNVERIFIED")
        self.assertEqual(result["latency"]["metrics"]["full_turn"]["status"], "NOT_MEASURED")

    def test_missing_png_and_digest_mismatch_excluded(self):
        cases = [self.case(i) for i in range(2)]
        (self.root / "image-0.png").unlink()
        (self.root / "image-1.png").write_bytes(png_bytes((4, 5, 6)))
        result = self.run_index(cases)
        self.assertEqual(result["verified_png_files"], 0)
        self.assertEqual(result["human_attested_real_cases"], 0)
        self.assertEqual(len(result["issues"]), 2)

    def test_symlink_and_traversal_rejected(self):
        case = self.case(0)
        (self.root / "linked.png").symlink_to(self.root / "image-0.png")
        case["artifact"]["png_path"] = "linked.png"
        self.assertEqual(self.run_index([case])["verified_png_files"], 0)
        case["artifact"]["png_path"] = "../image-0.png"
        self.assertEqual(self.run_index([case])["verified_png_files"], 0)

    def test_receipt_mismatch_and_missing_reviewer_excluded(self):
        case = self.case(0)
        case["artifact"]["receipt_sha256"] = "a" * 64
        self.assertEqual(self.run_index([case])["human_attested_real_cases"], 0)
        case = self.case(1)
        case["human_label"].pop("reviewed_at")
        self.assertEqual(self.run_index([case])["human_attested_real_cases"], 0)

    def test_unobservable_not_g2_pass_and_qa_unsafe_pass_counted(self):
        cases = [self.case(0, status="unobservable", qa="passed"),
                 self.case(1, status="violated", qa="passed"),
                 self.case(2, status="verified", qa="rejected")]
        result = self.run_index(cases)
        self.assertEqual(result["human_attested_real_cases"], 3)
        self.assertEqual(result["quality"]["confusion"]["fp"], 1)
        self.assertEqual(result["quality"]["confusion"]["fn"], 1)
        self.assertEqual(result["quality"]["unsafe_pass_on_unlabeled"], 1)
        self.assertFalse(result["release_eligible"])

    def test_missing_qa_does_not_fabricate_accuracy(self):
        case = self.case(0)
        case.pop("qa")
        result = self.run_index([case])
        self.assertEqual(result["human_attested_real_cases"], 1)
        self.assertEqual(result["quality"]["status"], "NOT_MEASURED")
        self.assertEqual(result["missing_qa"], 1)

    def test_wrong_frame_latency_excluded(self):
        case = self.case(0)
        observation = {
            "scene_id": case["scene_id"],
            "outcome": "rejected",
            "provenance": dict(case["provenance"]),
            "stages": {},
        }
        observation["provenance"]["png_sha256"] = "f" * 64
        result = self.run_index([case], [observation])
        self.assertEqual(result["latency"]["valid_observations"], 0)
        self.assertEqual(result["latency"]["metrics"]["full_turn"]["status"], "NOT_MEASURED")

    def test_private_paths_and_ids_not_leaked_in_report(self):
        case = self.case(0)
        case["artifact"]["png_path"] = "secret-story/actor-face.png"
        result = self.run_index([case])
        encoded = json.dumps(result)
        self.assertNotIn("secret-story", encoded)
        self.assertNotIn("actor-face", encoded)


if __name__ == "__main__":
    unittest.main()
