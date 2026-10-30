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
    def test_codex_toolless_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory) / "events.jsonl"
            p.write_text(json.dumps({"type": "item.completed", "item": {
                "type": "agent_message", "text": "I cannot use tools"}}) + "\n")
            self.assertEqual(mod.tool_event_verdict(p), "no_tool_execution")

    def test_codex_code_host_failure_detected_despite_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory) / "events.jsonl"
            p.write_text(json.dumps({"type": "item.completed", "item": {
                "type": "error", "message": "Code Mode is unavailable; host executable was not found"}}) + "\n")
            self.assertEqual(mod.tool_event_verdict(p), "tool_failure")

    def test_codex_real_commands_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory) / "events.jsonl"
            p.write_text(json.dumps({"type": "item.completed", "item": {
                "type": "command_execution", "exit_code": 0}}) + "\n")
            self.assertEqual(mod.tool_event_verdict(p), "ok")

    def test_git_snapshot_includes_untracked(self):
        def fake_command(args, **kwargs):
            if "rev-parse" in args:
                return mock.Mock(stdout="cafebabefeed\n")
            self.assertNotIn("-uno", args)
            return mock.Mock(stdout="?? new_file.py\n M existing.py\n")
        with mock.patch.object(mod, "command", side_effect=fake_command):
            snapshot = mod.git_snapshot()
        self.assertEqual(snapshot["changed_files"], 2)

    def test_mission_script_is_required_before_iteration(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "night-agent.py").read_text()
        self.assertIn('mission_script = ROOT / "bin/night-mission.py"', source)
        self.assertIn('blocked_mission_controller', source)
        self.assertIn('mission["instruction"]', source)

    def test_mission_not_masked_by_time_completion(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "night-agent.py").read_text()
        self.assertIn('"blocked_human_gate"', source)

    def test_usage_aggregation_does_not_read_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            fp = pathlib.Path(directory) / "run.jsonl"
            fp.write_text(
                json.dumps({"type":"item.completed","item":{"type":"command_execution",
                         "aggregated_output":"short"}}) + "\n" +
                json.dumps({"type":"turn.completed","usage":{"input_tokens":300,
                         "cached_input_tokens":250,"output_tokens":20}}) + "\n")
            result=mod.extract_completed_usage(fp)
            self.assertEqual(result["input_tokens"],300)
            self.assertEqual(result["cached_input_tokens"],250)
            self.assertEqual(result["completed_commands"],1)
            self.assertEqual(result["tool_output_characters"],5)

    def test_default_model(self):
        self.assertEqual(mod.MODEL_DEFAULT, "gpt-6-astra")
    def test_default_task_is_nonproduction(self):
        self.assertIn("non-publishing",mod.DEFAULT_TASK)
        self.assertIn("No production",mod.DEFAULT_TASK)
if __name__=="__main__":
    unittest.main()
