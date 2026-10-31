"""Offline adversarial native-pose dispatcher tests. No GPU or game writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("autonomous_dispatch_pose_test", HERE / "autonomous_dispatch.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import pose_graph_native as pose


def node_info():
    return {
        "LoadImage": {"input": {"required": {"image": [[]]}}},
        "ImageScale": {"input": {"required": {
            k: ["test"] for k in ("image", "width", "height", "crop", "upscale_method")}}},
        "ModelPatchLoader": {"input": {"required": {"name": [[pose.POSE_PATCH_NAME]]}}},
        "ZImageFunControlnet": {"input": {"required": {
            k: ["test"] for k in ("model", "model_patch", "vae", "strength")},
            "optional": {"image": ["IMAGE"]}}},
    }


class NativePoseOneFactorTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.home = Path(t.name)
        self.root = self.home / "lab" / "autonomous"
        self.case = m.r.load_case("CG-03")
        self.plan = {
            "schema": "firstshot_one_factor_v1",
            "id": "CG03_NATIVEPOSE_R15",
            "case": "CG-03",
            "base_case_sha256": m.base_sha("CG-03"),
            "factor": "native_pose",
            "new_value": pose.POSE_GUIDE_SHA256,
            "hypothesis": "Native Union conditioning with the SHA-pinned rear-oblique guide may fix the previously incorrect wall-lean view.",
            "falsifier": "The exact original output still lacks a forward torso lean, full boots, actual hand-wall contact, or the rear-oblique view.",
            "author_task": "R-15",
        }

    def _guide(self):
        source = self.home / ".local/share/mcp-vn-comfy/input/wall_push_rear_oblique_01.png"
        source.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1216, 704), (32, 44, 60)).save(source)
        return source, hashlib.sha256(source.read_bytes()).hexdigest()

    def test_native_pose_strict_sha_and_scene(self):
        self.assertIs(m.validate(self.plan), self.plan)
        with self.assertRaisesRegex(ValueError, "unapproved_native_pose"):
            m.validate({**self.plan, "new_value": "0" * 64})
        with self.assertRaises(ValueError):
            m.validate({**self.plan, "factor": "checkpoint"})
        for other in ("BG-01", "CG-02", "SPR-01"):
            wrong = {**self.plan, "case": other, "base_case_sha256": m.base_sha(other)}
            with self.assertRaisesRegex(ValueError, "unapproved_native_pose"):
                m.validate(wrong)

    def test_actual_guide_stages_once_and_only_sampler_model_changes(self):
        source, digest = self._guide()
        plan = {**self.plan, "new_value": digest}
        with patch.object(pose, "POSE_GUIDE_SHA256", digest), \
             patch.object(m.Path, "home", return_value=self.home), \
             patch.object(m.r, "api", return_value=node_info()):
            m.validate(plan)
            graph, evidence = m.build_graph_for_plan(plan, self.case, "vn_zimage_probe_ab_nativepose_")
        baseline = m.z.create_graph(
            self.case["prompt"], seed=self.case["seed"], prefix="vn_zimage_probe_ab_nativepose_",
            width=self.case["canvas"][0], height=self.case["canvas"][1], private_unanchored=True)
        self.assertEqual(set(graph) - set(baseline), {"11", "12", "13", "14"})
        self.assertEqual(graph["8"]["inputs"]["model"], ["14", 0])
        graph["8"]["inputs"]["model"] = ["6", 0]
        for key in baseline:
            self.assertEqual(graph[key], baseline[key])
        staged = source.with_name("vn_pose_probe_cg03_nativepose_r15.png")
        self.assertEqual(hashlib.sha256(staged.read_bytes()).hexdigest(), digest)
        self.assertEqual(evidence["pose_guide_sha256"], digest)
        self.assertEqual(evidence["staged_pose_filename"], staged.name)

    def test_staged_file_collision_never_overwrites(self):
        source, digest = self._guide()
        target = source.with_name("vn_pose_probe_cg03_nativepose_r15.png")
        target.write_bytes(b"other-owner-file")
        plan = {**self.plan, "new_value": digest}
        with patch.object(pose, "POSE_GUIDE_SHA256", digest), \
             patch.object(m.Path, "home", return_value=self.home), \
             patch.object(m.r, "api", return_value=node_info()):
            with self.assertRaises(FileExistsError):
                m.build_graph_for_plan(plan, self.case, "vn_zimage_probe_ab_nativepose_")
        self.assertEqual(target.read_bytes(), b"other-owner-file")

    def test_missing_union_metadata_blocks_before_prompt_post(self):
        _, digest = self._guide()
        plan = {**self.plan, "new_value": digest}
        endpoints = []
        def api(endpoint, *args, **kwargs):
            endpoints.append(endpoint)
            return {}
        with patch.object(pose, "POSE_GUIDE_SHA256", digest), \
             patch.object(m.Path, "home", return_value=self.home), \
             patch.object(m.r, "queue_empty", return_value=True), \
             patch.object(m.r, "api", side_effect=api):
            self.assertTrue(m.queue(self.root, plan)["enqueued"])
            result = m.tick(self.root)
        self.assertEqual(result["status"], "BLOCKED_INVALID_PLAN")
        self.assertEqual(endpoints, ["/object_info"])
        self.assertFalse(list((self.root / "pending").glob("*.json")))
        self.assertEqual(len(list((self.root / "blocked").glob("*.json"))), 1)

    def test_native_pose_unknown_running_never_submitted(self):
        m.setup(self.root)
        (self.root / "running" / (self.plan["id"] + ".json")).write_text("{}")
        with patch.object(m.r, "api", side_effect=AssertionError("GPU requested")):
            self.assertEqual(m.tick(self.root)["status"], "STOP_UNKNOWN_PREVIOUS_SUBMISSION")


if __name__ == "__main__":
    unittest.main()
