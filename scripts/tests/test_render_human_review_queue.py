"""Offline synthetic fixtures ONLY. Never substitute for human-reviewed PNG."""
import copy
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_human_review_queue import build_queue, write_private_queue
from test_render_golden_evidence_index import png_bytes


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class ReviewQueueTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.key = b"private-test-capture-signing-key-123456"

    def candidate(self, i, *, origin="real_comfy_job", signed=True, auto=False):
        scene = f"private-scene-{i}"
        raw = png_bytes((i % 256, (i // 256) % 256, 9))
        png_sha = digest(raw)
        (self.root / f"frame-{i}.png").write_bytes(raw)
        contract = {
            "schema_version": 1, "scene_id": scene, "kind": "cg",
            "required_facts": [
                {"fact_id": "wardrobe", "attribute": "wardrobe",
                 "mandatory": True, "expectation": "navy jacket"},
                {"fact_id": "contact", "attribute": "contact",
                 "mandatory": True, "expectation": "both hands on prop"}
            ],
        }
        contract_raw = canonical(contract)
        (self.root / f"contract-{i}.json").write_bytes(contract_raw)
        candidate = {
            "scene_id": scene, "frame_id": f"frame-{i}", "job_id": f"job-{i}",
            "prompt_id": f"prompt-{i}", "kind": "cg",
            "png_path": f"frame-{i}.png", "png_sha256": png_sha,
            "contract_path": f"contract-{i}.json",
            "contract_sha256": digest(contract_raw),
            "receipt_path": f"receipt-{i}.json",
            "source_sha256": digest(f"source-{i}".encode()),
            "reference_sha256": digest(f"reference-{i}".encode()),
        }
        receipt = {
            "capture_kind": origin, "captured_at": "2026-10-31T07:00:00Z",
            **{k: candidate[k] for k in (
                "scene_id", "frame_id", "job_id", "prompt_id", "kind",
                "png_sha256", "contract_sha256", "source_sha256",
                "reference_sha256")},
        }
        if signed:
            receipt["signature"] = {
                "scheme": "hmac-sha256-v1", "key_id": "capture-local-v1",
                "mac": hmac.new(self.key, canonical(receipt), hashlib.sha256).hexdigest(),
            }
        (self.root / f"receipt-{i}.json").write_bytes(canonical(receipt))
        if auto:
            candidate["human_label"] = {"status": "verified", "reviewer_type": "human"}
        return candidate

    def run_queue(self, candidates, inventory=None):
        return build_queue({"schema_version": 1, "candidates": candidates},
                           self.root, self.key, inventory=inventory)

    def test_valid_real_signed_case_is_only_pending(self):
        queue, report = self.run_queue([self.candidate(1)])
        self.assertEqual(report["queued_for_human_review"], 1)
        self.assertEqual(report["human_labels"], 0)
        self.assertFalse(report["release_eligible"])
        self.assertEqual(report["g2"], "UNVERIFIED")
        self.assertEqual(queue["cases"][0]["review"]["state"], "awaiting_independent_human")
        self.assertIsNone(queue["cases"][0]["review"]["facts"][0]["verdict"])
        self.assertIsNone(queue["cases"][0]["review"]["reviewer_id"])

    def test_red_thirty_duplicates_cannot_satisfy_release(self):
        item = self.candidate(0)
        queue, report = self.run_queue([copy.deepcopy(item) for _ in range(30)])
        self.assertEqual(report["queued_for_human_review"], 1)
        self.assertEqual(report["rejected_duplicate"], 29)
        self.assertFalse(report["release_eligible"])
        self.assertEqual(report["human_labels"], 0)

    def test_red_thirty_auto_labels_are_rejected(self):
        queue, report = self.run_queue([self.candidate(i, auto=True) for i in range(30)])
        self.assertEqual(len(queue["cases"]), 0)
        self.assertEqual(report["rejected_untrusted"], 30)
        self.assertEqual(report["human_labels"], 0)

    def test_red_thirty_synthetic_receipts_are_rejected(self):
        queue, report = self.run_queue([self.candidate(i, origin="synthetic") for i in range(30)])
        self.assertEqual(len(queue["cases"]), 0)
        self.assertEqual(report["rejected_untrusted"], 30)

    def test_unsigned_and_wrong_mac_rejected(self):
        a = self.candidate(0, signed=False)
        b = self.candidate(1)
        receipt = self.root / b["receipt_path"]
        data = json.loads(receipt.read_text())
        data["signature"]["mac"] = "f" * 64
        receipt.write_bytes(canonical(data))
        queue, report = self.run_queue([a, b])
        self.assertEqual(len(queue["cases"]), 0)
        self.assertEqual(report["rejected_untrusted"], 2)

    def test_png_and_contract_tampering_rejected(self):
        a, b = self.candidate(0), self.candidate(1)
        (self.root / a["png_path"]).write_bytes(png_bytes((8, 8, 8)))
        (self.root / b["contract_path"]).write_text("{}")
        queue, report = self.run_queue([a, b])
        self.assertEqual(len(queue["cases"]), 0)
        self.assertEqual(report["rejected_untrusted"], 2)

    def test_missing_mandatory_fact_rejected(self):
        a = self.candidate(0)
        contract = {"schema_version": 1, "scene_id": a["scene_id"],
                    "kind": "cg", "required_facts": []}
        raw = canonical(contract)
        (self.root / a["contract_path"]).write_bytes(raw)
        a["contract_sha256"] = digest(raw)
        receipt = self.root / a["receipt_path"]
        obj = json.loads(receipt.read_text())
        obj["contract_sha256"] = digest(raw)
        obj.pop("signature")
        obj["signature"] = {
            "scheme": "hmac-sha256-v1", "key_id": "capture-local-v1",
            "mac": hmac.new(self.key, canonical(obj), hashlib.sha256).hexdigest(),
        }
        receipt.write_bytes(canonical(obj))
        queue, report = self.run_queue([a])
        self.assertEqual(len(queue["cases"]), 0)
        self.assertEqual(report["rejected_untrusted"], 1)

    def test_symlink_and_traversal_rejected(self):
        a = self.candidate(0)
        (self.root / "alias.png").symlink_to(self.root / a["png_path"])
        a["png_path"] = "alias.png"
        b = self.candidate(1)
        b["png_path"] = "../outside.png"
        queue, report = self.run_queue([a, b])
        self.assertEqual(len(queue["cases"]), 0)
        self.assertEqual(report["rejected_untrusted"], 2)

    def test_contract_sha_must_be_distinct(self):
        a, b = self.candidate(0), self.candidate(1)
        b["contract_sha256"] = a["contract_sha256"]
        queue, report = self.run_queue([a, b])
        self.assertEqual(report["queued_for_human_review"], 1)
        self.assertEqual(report["rejected_duplicate"], 1)

    def test_inventory_counts_only_cannot_create_cases(self):
        inventory = {"candidate_png_files": 192, "unique_png_sha": 183,
                     "human_labels_independently_verified": 0}
        queue, report = build_queue(None, self.root, None, inventory=inventory)
        self.assertEqual(queue["cases"], [])
        self.assertEqual(report["inventory_candidate_png_files"], 192)
        self.assertEqual(report["inventory_unique_png_sha"], 183)
        self.assertEqual(report["queued_for_human_review"], 0)
        self.assertEqual(report["human_labels"], 0)

    def test_cli_absolute_paths_under_private_root_alias(self):
        private = self.root / "private"
        private.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(private, target_is_directory=True)
        (private / "inventory.json").write_text(json.dumps({
            "candidate_png_files": 192, "unique_png_sha": 183}))
        script = Path(__file__).resolve().parents[1] / "render_human_review_queue.py"
        run = subprocess.run([
            sys.executable, str(script), "--private-root", str(alias),
            "--inventory", str(alias / "inventory.json"),
            "--output", str(alias / "queue.json"),
        ], capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(json.loads(run.stdout)["queued_for_human_review"], 0)
        self.assertEqual((private / "queue.json").stat().st_mode & 0o777, 0o600)

    def test_private_output_exclusive_and_no_path_leak(self):
        queue, report = self.run_queue([self.candidate(0)])
        output = self.root / "private-review-queue.json"
        write_private_queue(output, self.root, queue)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            write_private_queue(output, self.root, queue)
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertNotIn("private-scene-0", json.dumps(report))
        self.assertNotIn("navy jacket", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
