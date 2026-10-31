"""CPU-only regression suite; never talks to Comfy, never uses GPU."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("first_shot_runner",HERE/"run_one.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FirstShotTests(unittest.TestCase):
    def test_pack_exactly_five_distinct_first_shots(self):
        payload=json.loads(mod.PACK.read_text())
        self.assertEqual([x["id"] for x in payload["cases"]],
                         ["BG-01","SPR-01","CG-01","CG-02","CG-03"])
        self.assertEqual(len({c["seed"] for c in payload["cases"]}),5)
        for c in payload["cases"]:
            self.assertTrue(c["prompt"])
            self.assertTrue(c["expected"])
            self.assertTrue(all(isinstance(n,int) and 256<=n<=1024 for n in c["canvas"]))
    def test_frozen_canary_graph_has_no_game_publish_nodes(self):
        for item in json.loads(mod.PACK.read_text())["cases"]:
            with patch.object(mod,"queue_empty",return_value=True):
                g,d,p=mod.preflight(item,Path("/tmp"))
            self.assertEqual(g["8"]["inputs"]["seed"],item["seed"])
            self.assertEqual(g["10"]["class_type"],"SaveImage")
            self.assertIn("vn_zimage_probe_fs_",p)
            self.assertEqual(len(d),64)
    def test_preflight_is_read_only_zero_gpu(self):
        with tempfile.TemporaryDirectory() as t, patch.object(mod,"queue_empty",return_value=True),patch.object(mod,"api",side_effect=AssertionError("no API submit")):
            # preflight does query queue; patch queue_empty to avoid it.
            x=mod.run("BG-01",Path(t)/"case",submit=False)
            self.assertEqual(x["status"],"PREFLIGHT_ONLY")
            self.assertEqual(x["gpu_jobs"],0)
            self.assertFalse((Path(t)/"case/BG-01-result.json").exists())
    def test_busy_gpu_fails_before_submit(self):
        with tempfile.TemporaryDirectory() as t, patch.object(mod,"queue_empty",return_value=False):
            with self.assertRaisesRegex(RuntimeError,"GPU_QUEUE_BUSY"):
                mod.run("BG-01",Path(t)/"case",submit=True)
    def test_unknown_case_is_denied(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):
                mod.run("../bad",Path(t),submit=True)

if __name__=="__main__":unittest.main()
