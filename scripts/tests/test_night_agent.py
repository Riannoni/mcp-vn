"""Read-only unit tests for the night agent's quota logic and status."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

FILE = pathlib.Path(__file__).resolve().parents[1] / "night-agent.py"
spec = importlib.util.spec_from_file_location("vn_night_agent", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class NightTests(unittest.TestCase):
    def test_quota_ok(self):
        sample = {"accounts": [{"provider":"codex","status":"ok","allowed":True,
          "windows":{"5h_or_primary":{"used_percent":2},"7d_or_secondary":{"used_percent":9}}}]}
        with mock.patch.object(mod,"command",return_value=mock.Mock(returncode=0,stdout=json.dumps(sample))):
            ok, q = mod.quota_check()
        self.assertTrue(ok)
        self.assertEqual(q["weekly_used_percent"],9)
    def test_quota_missing_is_not_free(self):
        sample = {"accounts":[{"provider":"codex","status":"unavailable"}]}
        with mock.patch.object(mod,"command",return_value=mock.Mock(returncode=0,stdout=json.dumps(sample))):
            ok, q = mod.quota_check()
        self.assertFalse(ok)
    def test_quota_guard_stops_85_percent(self):
        sample={"accounts":[{"provider":"codex","status":"ok","allowed":True,"windows":{
            "5h_or_primary":{"used_percent":3},"7d_or_secondary":{"used_percent":85}}}]}
        with mock.patch.object(mod,"command",return_value=mock.Mock(returncode=0,stdout=json.dumps(sample))):
            ok, q=mod.quota_check()
        self.assertFalse(ok)
        self.assertEqual(q["status"],"guarded")
    def test_quota_exhausted_stops(self):
        sample={"accounts":[{"provider":"codex","status":"ok","allowed":False,
            "windows":{"5h_or_primary":{"used_percent":0},"7d_or_secondary":{"used_percent":0}}}]}
        with mock.patch.object(mod,"command",return_value=mock.Mock(returncode=0,stdout=json.dumps(sample))):
            ok, q=mod.quota_check()
        self.assertFalse(ok)
    def test_atomic_status_json(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/"status.json"
            mod.write_json(path,{"state":"working","iteration":3})
            self.assertEqual(mod.read_json(path)["iteration"],3)
    def test_default_model(self):
        self.assertEqual(mod.MODEL_DEFAULT, "gpt-6-astra")
    def test_default_task_is_nonproduction(self):
        self.assertIn("non-publishing",mod.DEFAULT_TASK)
        self.assertIn("No production",mod.DEFAULT_TASK)
if __name__=="__main__":
    unittest.main()
