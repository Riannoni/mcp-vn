"""Synthetic, offline contract tests; never load private game images."""
import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_golden_set_audit import audit_manifest


def digest(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def example_case(number):
    scene = f"scene-{number:03d}"
    frame = f"frame-{number:03d}"
    png = digest("png-" + scene)
    source = digest("source-" + scene)
    ref = digest("reference-" + scene)
    evidence = {
        "scene_id": scene,
        "frame_id": frame,
        "png_sha256": png,
        "source_sha256": source,
        "method": "independent_original_pixel_review",
        "observation": "synthetic observation, not real visual evidence",
    }
    return {
        "scene_id": scene,
        "kind": "cg",
        "source_sha256": source,
        "reference_sha256": ref,
        "provenance": {
            "scene_id": scene,
            "frame_id": frame,
            "png_sha256": png,
            "source_sha256": source,
            "contract_sha256": digest("contract-" + scene),
            "job_id": "job-" + scene,
            "prompt_id": "prompt-" + scene,
        },
        "named_actors": [
            {"actor_id": "actor-a", "status": "verified", "evidence": dict(evidence)}
        ],
        "required_objects": [
            {"object_id": "map", "status": "verified", "evidence": dict(evidence)}
        ],
        "human_label": {
            "status": "verified",
            "reviewer_id": "reviewer-1",
            "method": "original_pixels",
            "reviewed_png_sha256": png,
            "observation": "synthetic label; not an inspected original",
        },
    }


def manifest(count=30):
    return {"schema_version": 1, "cases": [example_case(i) for i in range(count)]}


class GoldenSetAuditTest(unittest.TestCase):
    def test_synthetic_thirty_schema_valid_never_proves_g2(self):
        result = audit_manifest(manifest())
        self.assertTrue(result["manifest_valid"], result["issues"])
        self.assertEqual(result["case_count"], 30)
        self.assertEqual(result["declared_complete_cases"], 30)
        self.assertFalse(result["release_eligible"])
        self.assertEqual(result["g2_status"], "NOT_INDEPENDENTLY_VERIFIED")

    def test_minimum_thirty_enforced(self):
        result = audit_manifest(manifest(29))
        self.assertFalse(result["manifest_valid"])

    def test_duplicate_scene_rejected(self):
        doc = manifest()
        doc["cases"][1]["scene_id"] = doc["cases"][0]["scene_id"]
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_duplicate_frame_rejected(self):
        doc = manifest()
        doc["cases"][1]["provenance"]["frame_id"] = doc["cases"][0]["provenance"]["frame_id"]
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_reused_output_or_job_not_independent(self):
        for field in ("png_sha256", "job_id", "prompt_id"):
            with self.subTest(field=field):
                doc = manifest()
                doc["cases"][1]["provenance"][field] = doc["cases"][0]["provenance"][field]
                if field == "png_sha256":
                    png = doc["cases"][0]["provenance"]["png_sha256"]
                    for collection in ("named_actors", "required_objects"):
                        for item in doc["cases"][1][collection]:
                            item["evidence"]["png_sha256"] = png
                    doc["cases"][1]["human_label"]["reviewed_png_sha256"] = png
                self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_reused_contract_digest_is_not_an_independent_scene(self):
        # Distinct scene/frame/job/PNG IDs must not make one unchanged
        # scene contract count as 30 independent human-labeled scenes.
        doc = manifest()
        same_contract = doc["cases"][0]["provenance"]["contract_sha256"]
        for case in doc["cases"][1:]:
            case["provenance"]["contract_sha256"] = same_contract
        result = audit_manifest(doc)
        self.assertFalse(result["manifest_valid"], result)
        self.assertTrue(any("duplicate provenance.contract_sha256" in issue
                            for issue in result["issues"]), result)

    def test_provenance_cross_scene_rejected(self):
        doc = manifest()
        doc["cases"][0]["provenance"]["scene_id"] = "other-scene"
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_evidence_cross_frame_rejected(self):
        doc = manifest()
        doc["cases"][0]["required_objects"][0]["evidence"]["frame_id"] = "frame-other"
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_evidence_cross_source_rejected(self):
        doc = manifest()
        doc["cases"][0]["named_actors"][0]["evidence"]["source_sha256"] = digest("other")
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_evidence_cross_png_rejected(self):
        doc = manifest()
        doc["cases"][0]["required_objects"][0]["evidence"]["png_sha256"] = digest("other")
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_missing_source_reference_sha_rejected(self):
        for key in ("source_sha256", "reference_sha256"):
            with self.subTest(key=key):
                doc = manifest()
                doc["cases"][0].pop(key)
                self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_bad_hash_and_missing_label_rejected(self):
        doc = manifest()
        doc["cases"][0]["reference_sha256"] = "not-a-sha"
        self.assertFalse(audit_manifest(doc)["manifest_valid"])
        doc = manifest()
        doc["cases"][0].pop("human_label")
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_unobservable_is_valid_annotation_not_declared_pass(self):
        doc = manifest()
        doc["cases"][0]["required_objects"][0]["status"] = "unobservable"
        result = audit_manifest(doc)
        self.assertTrue(result["manifest_valid"], result["issues"])
        self.assertEqual(result["declared_complete_cases"], 29)
        self.assertEqual(result["blocked_cases"], 1)
        self.assertFalse(result["release_eligible"])

    def test_human_unobservable_blocks(self):
        doc = manifest()
        doc["cases"][0]["human_label"]["status"] = "unobservable"
        result = audit_manifest(doc)
        self.assertTrue(result["manifest_valid"], result["issues"])
        self.assertEqual(result["blocked_cases"], 1)

    def test_mandatory_not_applicable_rejected(self):
        doc = manifest()
        doc["cases"][0]["required_objects"][0]["status"] = "not_applicable"
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_missing_actor_list_rejected(self):
        doc = manifest()
        doc["cases"][0].pop("named_actors")
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_empty_actor_for_cg_rejected(self):
        doc = manifest()
        doc["cases"][0]["named_actors"] = []
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_background_can_have_no_named_actor_or_required_object(self):
        doc = manifest()
        doc["cases"][0]["kind"] = "background"
        doc["cases"][0]["named_actors"] = []
        doc["cases"][0]["required_objects"] = []
        self.assertTrue(audit_manifest(doc)["manifest_valid"])

    def test_duplicate_actor_and_object_rejected(self):
        for key in ("named_actors", "required_objects"):
            with self.subTest(key=key):
                doc = manifest()
                doc["cases"][0][key].append(copy.deepcopy(doc["cases"][0][key][0]))
                self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_missing_evidence_observation_rejected(self):
        doc = manifest()
        doc["cases"][0]["named_actors"][0]["evidence"].pop("observation")
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_mismatched_human_png_rejected(self):
        doc = manifest()
        doc["cases"][0]["human_label"]["reviewed_png_sha256"] = digest("other")
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_untrusted_human_method_rejected(self):
        doc = manifest()
        doc["cases"][0]["human_label"]["method"] = "thumbnail"
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_unhashable_fields_fail_closed(self):
        for path in (("kind",), ("human_label", "status"),
                     ("required_objects", 0, "status")):
            with self.subTest(path=path):
                doc = manifest()
                target = doc["cases"][0]
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = []
                self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_cross_scene_annotation_rejected(self):
        doc = manifest()
        doc["cases"][0]["named_actors"][0]["evidence"]["scene_id"] = "other-scene"
        self.assertFalse(audit_manifest(doc)["manifest_valid"])

    def test_malformed_root_rejected(self):
        self.assertFalse(audit_manifest([])["manifest_valid"])
        self.assertFalse(audit_manifest({"schema_version": 1, "cases": "bad"})["manifest_valid"])


if __name__ == "__main__":
    unittest.main()
