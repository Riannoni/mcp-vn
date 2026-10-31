"""Adversarial immutable-baseline regression: CPU only, no Comfy submission."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

BASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE / "worker"))
sys.path.insert(0, str(BASE / "scripts" / "first_shot"))
import zimage_backend
import pose_graph_native as pose

PACK = json.loads((BASE / "scripts/first_shot/pack-v1.json").read_text())
CASE = next(c for c in PACK["cases"] if c["id"] == "CG-03")
NODES = {n: {"input": {"required": {k: [] for k in fields}}} for n, fields in {
    "LoadImage": ["image"],
    "ImageScale": ["image", "upscale_method", "width", "height", "crop"],
    "ModelPatchLoader": ["name"],
    "ZImageFunControlnet": ["model", "model_patch", "vae", "strength"],
}.items()}
NODES["ModelPatchLoader"]["input"]["required"]["name"] = [[pose.POSE_PATCH_NAME]]


def baseline(prefix="vn_zimage_probe_baselinepin"):
    return zimage_backend.create_graph(
        CASE["prompt"], seed=CASE["seed"], prefix=prefix,
        width=CASE["canvas"][0], height=CASE["canvas"][1],
        private_unanchored=True,
    )


def build(graph=None, case=None):
    return pose.add_native_pose_to_frozen_cg03(
        baseline() if graph is None else graph,
        CASE if case is None else case,
        staged_guide_name="vn_pose_probe_rear_sha.png",
        object_info=NODES,
    )


class FrozenGraphProvenanceTests(unittest.TestCase):
    def test_reject_all_five_independently_confirmed_second_factors(self):
        mutations = {
            "unet_changed": lambda g: g["1"]["inputs"].update(unet_name="unauthorized.safetensors"),
            "encoder_changed": lambda g: g["2"]["inputs"].update(clip_name="unauthorized.safetensors"),
            "vae_changed": lambda g: g["3"]["inputs"].update(vae_name="unauthorized.safetensors"),
            "sampling_shift_changed": lambda g: g["6"]["inputs"].update(shift=9),
            "decoded_samples_changed": lambda g: g["9"]["inputs"].update(samples=["5", 0]),
        }
        for name, mutate in mutations.items():
            g = baseline()
            mutate(g)
            with self.subTest(name=name), self.assertRaises(pose.NativePoseUnavailable):
                build(g)
        g = baseline()
        modified = deepcopy(CASE)
        modified["prompt"] = "changed " + modified["prompt"]
        g["4"]["inputs"]["text"] = modified["prompt"]
        with self.assertRaises(pose.NativePoseUnavailable):
            build(g, modified)

    def test_entire_original_graph_is_immutable_except_safe_prefix(self):
        g = baseline("vn_zimage_probe_otherprefix")
        output = build(g)
        self.assertEqual(g["8"]["inputs"]["model"], ["6", 0])
        self.assertEqual(output["8"]["inputs"]["model"], ["14", 0])
        self.assertEqual(output["10"]["inputs"]["filename_prefix"],
                         "vn_zimage_probe_otherprefix")
        self.assertEqual(set(output) - set(g), {"11", "12", "13", "14"})

    def test_case_extra_field_must_not_override_frozen_contract(self):
        with self.assertRaises(pose.NativePoseUnavailable):
            build(case=CASE | {"source_state": "forge"})

    def test_modified_frozen_pack_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "pack.json"
            fake.write_bytes((BASE / "scripts/first_shot/pack-v1.json").read_bytes() + b"\n")
            with mock.patch.object(pose, "_PACK_PATH", fake, create=True):
                with self.assertRaises(pose.NativePoseUnavailable):
                    build()

    def test_modified_backend_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "backend.py"
            fake.write_bytes((BASE / "worker/zimage_backend.py").read_bytes() + b"\n")
            with mock.patch.object(pose, "_BACKEND_PATH", fake, create=True):
                with self.assertRaises(pose.NativePoseUnavailable):
                    build()


if __name__ == "__main__":
    unittest.main()
