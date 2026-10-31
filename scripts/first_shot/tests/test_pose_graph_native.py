"""Independent CPU-only negatives: no GPU, network, secrets, or model downloads."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
import unittest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pose_graph_native as pose

CASE = {"id": "CG-03", "type": "cg", "seed": 202610310105,
        "canvas": [1024, 592], "prompt": "three quarter rear full body actress against wall"}
NODES = {n: {"input": {"required": {k: [] for k in fields}}} for n, fields in {
    "LoadImage": ["image"],
    "ImageScale": ["image", "upscale_method", "width", "height", "crop"],
    "ModelPatchLoader": ["name"],
    "ZImageFunControlnet": ["model", "model_patch", "vae", "strength"],
}.items()}
NODES["ModelPatchLoader"]["input"]["required"]["name"] = [[pose.POSE_PATCH_NAME]]


def base():
    classes = ["UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode",
               "ConditioningZeroOut", "ModelSamplingAuraFlow",
               "EmptySD3LatentImage", "KSampler", "VAEDecode", "SaveImage"]
    g = {str(i): {"class_type": kind, "inputs": {}} for i, kind in enumerate(classes, 1)}
    g["2"]["inputs"]["type"] = "lumina2"
    g["4"]["inputs"]["text"] = CASE["prompt"]
    g["7"]["inputs"].update(width=1024, height=592)
    g["8"]["inputs"].update(model=["6", 0], positive=["4", 0],
        negative=["5", 0], latent_image=["7", 0], seed=CASE["seed"],
        steps=8, cfg=1.0, sampler_name="res_multistep",
        scheduler="simple", denoise=1.0)
    g["10"]["inputs"]["filename_prefix"] = "vn_zimage_probe_abc"
    return g


def build(graph=None, case=None, nodes=None, filename="vn_pose_probe_rear_sha.png"):
    return pose.add_native_pose_to_frozen_cg03(
        graph if graph is not None else base(),
        case if case is not None else CASE,
        staged_guide_name=filename,
        object_info=nodes if nodes is not None else NODES)


class NativePoseGraphTests(unittest.TestCase):
    def test_only_one_factor_modifies_model_path(self):
        original = base()
        fixed = json.dumps(original, sort_keys=True)
        after = build(original)
        self.assertEqual(json.dumps(original, sort_keys=True), fixed)
        self.assertEqual(set(after) - set(original), {"11", "12", "13", "14"})
        self.assertEqual(after["8"]["inputs"]["model"], ["14", 0])
        self.assertEqual(after["14"]["inputs"]["model"], ["6", 0])
        self.assertEqual(after["14"]["inputs"]["model_patch"], ["13", 0])
        self.assertEqual(after["14"]["inputs"]["image"], ["12", 0])
        self.assertEqual(after["12"]["inputs"]["crop"], "disabled")
        self.assertEqual(after["13"]["inputs"]["name"], pose.POSE_PATCH_NAME)
        self.assertEqual(after["8"]["inputs"]["seed"], CASE["seed"])
        self.assertEqual(after["4"]["inputs"]["text"], CASE["prompt"])
        self.assertFalse(any("IPAdapter" in n["class_type"] or
            n["class_type"] == "ControlNetApply" for n in after.values()))

    def test_missing_patch_rejected_before_gpu(self):
        nodes = json.loads(json.dumps(NODES))
        nodes["ModelPatchLoader"]["input"]["required"]["name"] = [[]]
        with self.assertRaisesRegex(pose.NativePoseUnavailable, "patch_not_installed"):
            build(nodes=nodes)

    def test_missing_node_and_incompatible_signature(self):
        for key in ("ModelPatchLoader", "ZImageFunControlnet",
                    "ImageScale", "LoadImage"):
            nodes = json.loads(json.dumps(NODES))
            del nodes[key]
            with self.subTest(key=key), self.assertRaises(pose.NativePoseUnavailable):
                pose.validate_native_nodes(nodes)
        nodes = json.loads(json.dumps(NODES))
        del nodes["ZImageFunControlnet"]["input"]["required"]["model_patch"]
        with self.assertRaisesRegex(pose.NativePoseUnavailable, "signature"):
            pose.validate_native_nodes(nodes)

    def test_other_case_seed_size_prompt_and_sampler_rejected(self):
        for change in ({"id": "CG-02"}, {"seed": 4}, {"canvas": [1024, 576]}):
            with self.subTest(change=change), self.assertRaisesRegex(
                pose.NativePoseUnavailable, "not_frozen"):
                build(case=CASE | change)
        for key, value in (("seed", 42), ("steps", 3), ("model", ["1", 0])):
            g = base()
            g["8"]["inputs"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                pose.NativePoseUnavailable, "baseline_sampler"):
                build(graph=g)
        g = base()
        g["4"]["inputs"]["text"] = "different prompt"
        with self.assertRaisesRegex(pose.NativePoseUnavailable, "baseline_prompt"):
            build(graph=g)

    def test_staged_filename_rejects_path_traversal(self):
        for filename in ("../../x.png", "foo.png", "/tmp/private.png",
                         "vn_pose_probe_../x.png", "vn_pose_probe_a.png\\n",
                         "vn_pose_probe_hello.jpg"):
            with self.subTest(filename=filename), self.assertRaisesRegex(
                pose.NativePoseUnavailable, "invalid_filename"):
                build(filename=filename)

    def test_guide_verifies_actual_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "guide.png"
            Image.new("RGB", (1216, 704)).save(f)
            digest = hashlib.sha256(f.read_bytes()).hexdigest()
            self.assertEqual(pose.verify_private_guide(f, digest), digest)
            with self.assertRaisesRegex(pose.NativePoseUnavailable, "sha_mismatch"):
                pose.verify_private_guide(f, "0"*64)
            f.write_bytes(b"not an image")
            with self.assertRaisesRegex(pose.NativePoseUnavailable, "not_png"):
                pose.verify_private_guide(
                    f, hashlib.sha256(f.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
