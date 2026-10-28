#!/usr/bin/env python3
"""Non-generative regression tests for Model Lab checkpoint wiring."""
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("model_lab_test_target",ROOT/"server.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ID="0123456789abcdef0123456789abcdef"

class ModelSwitchTests(unittest.TestCase):
    def test_available_entries(self):
        for x in ("wai","cyberz","anima","pony"):
            self.assertIn(x,m.MODELS)
        for x in ("illustrious","zimage","klein","lustify","dreamshaper","realvis","juggernaut"):
            self.assertNotIn(x,m.MODELS)
        self.assertTrue(all(m.MODELS[x][2] for x in ("wai","cyberz","anima","pony")))

    def test_remaining_cyberrealistic_is_gguf(self):
        a=m.graph("cyberz","Two adults in a park","",768,768,3,ID)
        self.assertEqual(a["1"]["class_type"],"UnetLoaderGGUF")
        self.assertTrue(a["1"]["inputs"]["unet_name"].endswith("Q8_0.gguf"))
        self.assertEqual(a["8"]["inputs"]["steps"],8)

    def test_pony_and_wai_are_separate_canonical_styles(self):
        a=m.graph("pony","Landscape","",768,768,3,ID)
        b=m.graph("wai","Landscape","",768,768,3,ID)
        self.assertEqual(a["1"]["inputs"]["ckpt_name"],"CyberRealisticPony_V18.0_F16.safetensors")
        self.assertEqual(a["5"]["inputs"]["sampler_name"],"dpmpp_2m")
        self.assertEqual(b["1"]["inputs"]["ckpt_name"],"waiIllustriousSDXL_v170.safetensors")
        self.assertEqual(b["5"]["inputs"]["sampler_name"],"euler_ancestral")
        self.assertEqual(b["5"]["inputs"]["steps"],24)

    def test_anima_fusion_is_eight_step(self):
        a=m.graph("anima","Two adults sitting on a bench","",768,768,3,ID)
        self.assertEqual(a["7"]["inputs"]["steps"],8)
        self.assertEqual(a["7"]["inputs"]["cfg"],1)
        self.assertEqual(a["7"]["inputs"]["sampler_name"],"euler")
        self.assertIn("BASNSFW",a["1"]["inputs"]["unet_name"])

    def test_out_of_memory_message_is_human_readable(self):
        data={"messages":[("execution_error",{"exception_type":"torch.OutOfMemoryError",
              "exception_message":"CUDA out of memory. Tried to allocate 48 MiB",
              "node_type":"CLIPLoaderGGUF"})]}
        message=m.summarize_comfy_failure(data)
        self.assertIn("Недостаточно видеопамяти",message)
        self.assertNotIn("Traceback",message)

    def test_other_models_are_unchanged(self):
        for x in ("pony","wai"):
            self.assertEqual(m.graph(x,"A blue kite","",768,768,3,ID)["1"]["class_type"],
                             "CheckpointLoaderSimple")

if __name__=="__main__":
    unittest.main()
