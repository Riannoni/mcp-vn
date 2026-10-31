"""Source-only negative audit: direct Comfy /prompt must never be GPU-approved."""
import unittest

from scripts.render_gpu_submission_path_audit import (
    audit_submission_paths, scan_python_source, scan_text_source,
)


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.safe = {
            "listener": {"loopback": True, "observed": True},
            "queue": {"known": True, "running": 0, "pending": 0},
            "history_known": True,
            "exclusive_authority": True,
            "broker_enforced": True,
            "coverage_complete": True,
            "foreign_submit": False,
        }

    def check_block(self, sources, reason, **overrides):
        params = dict(self.safe)
        params.update(overrides)
        result = audit_submission_paths(sources, **params)
        self.assertEqual(result["status"], "denied")
        self.assertFalse(result["can_submit_gpu"])
        self.assertIn(reason, result["blockers"])
        return result

    def test_worker_direct_request_is_bypass(self):
        src = 'result=request(COMFY,"/prompt","POST",{"prompt": graph})'
        result = self.check_block({"worker/worker.py": src}, "direct_prompt_route_present")
        self.assertEqual(result["sinks"][0]["path"], "worker/worker.py")

    def test_pose_qa_direct_submit_is_bypass(self):
        src = 'response=request(comfy,"/prompt","POST",{"prompt": graph})'
        self.check_block({"worker/pose_geometry_runtime.py": src}, "direct_prompt_route_present")

    def test_reference_helper_post_json_is_bypass(self):
        src = 'result=_post_json(HOST+"/prompt",{"prompt": graph})'
        self.check_block({"worker/pose_reference_pipeline.py": src}, "direct_prompt_route_present")

    def test_urllib_request_data_is_bypass(self):
        src = 'req=urllib.request.Request(COMFY+"/prompt",data=b"{}")'
        self.check_block({"scripts/smoke-local-repair.py": src}, "direct_prompt_route_present")

    def test_javascript_route_is_conservative_bypass(self):
        src = 'await fetch(base + "/prompt", {method:"POST", body: payload})'
        self.check_block({"server.mjs": src}, "direct_prompt_route_present")

    def test_model_lab_direct_submit_is_bypass(self):
        src = 'result=comfy("/prompt",{"prompt": graph},30)'
        self.check_block({"standalone-web/server.py": src}, "direct_prompt_route_present")

    def test_js_comment_does_not_shift_sink_line(self):
        src = '// /prompt is a comment\nfetch("/prompt", {method:"POST"})'
        result = scan_text_source("src/a.js", src)
        self.assertEqual([item["line"] for item in result], [2])

    def test_foreign_submit_unknown_denies(self):
        self.check_block({"worker/a.py": "pass"}, "foreign_submit_unverifiable",
                         foreign_submit=None)

    def test_fstring_route_detected(self):
        src = 'url = f"{base}/prompt"'
        self.assertEqual(len(scan_python_source("worker/a.py", src)), 1)

    def test_docstring_is_not_a_sink(self):
        src = '"""Documentation about /prompt only."""\nVALUE = 1'
        self.assertEqual(scan_python_source("worker/a.py", src), [])

    def test_comments_are_not_sinks(self):
        self.assertEqual(scan_text_source("src/a.js", "// /prompt is forbidden\nconst x=1;"), [])

    def test_foreign_submit_denies_even_with_empty_queue(self):
        self.check_block({"worker/a.py": "pass"}, "foreign_submit_observed", foreign_submit=True)

    def test_unknown_queue_history_denies(self):
        self.check_block({"worker/a.py": "pass"}, "queue_history_unknown", history_known=False)

    def test_no_exclusive_authority_denies(self):
        self.check_block({"worker/a.py": "pass"}, "exclusive_authority_unproven", exclusive_authority=False)

    def test_unenforced_broker_denies(self):
        self.check_block({"worker/a.py": "pass"}, "broker_not_enforced", broker_enforced=False)

    def test_listener_not_observed_denies(self):
        self.check_block({"worker/a.py": "pass"}, "listener_untrusted",
                         listener={"loopback": True, "observed": False})

    def test_non_loopback_listener_denies(self):
        self.check_block({"worker/a.py": "pass"}, "listener_untrusted",
                         listener={"loopback": False, "observed": True})

    def test_unknown_queue_denies(self):
        self.check_block({"worker/a.py": "pass"}, "queue_unknown",
                         queue={"known": False, "running": 0, "pending": 0})

    def test_busy_queue_denies(self):
        self.check_block({"worker/a.py": "pass"}, "queue_busy",
                         queue={"known": True, "running": 1, "pending": 0})

    def test_incomplete_inventory_denies(self):
        self.check_block({"worker/a.py": "pass"}, "source_inventory_incomplete",
                         coverage_complete=False)

    def test_malformed_python_denies(self):
        self.check_block({"worker/a.py": "def broken(:"}, "source_inventory_incomplete")

    def test_empty_inventory_denies(self):
        self.check_block({}, "source_inventory_incomplete")

    def test_perfect_mock_is_not_real_gpu_permission(self):
        self.check_block({"worker/a.py": "pass"}, "source_only_not_live_authority")

    def test_sink_reports_only_location_not_source_contents(self):
        result = self.check_block(
            {"worker/a.py": 'request(COMFY,"/prompt","POST",{"secret":"PRIVATE"})'},
            "direct_prompt_route_present")
        self.assertNotIn("PRIVATE", str(result))
        self.assertEqual(result["sinks"][0]["line"], 1)


if __name__ == "__main__":
    unittest.main()
