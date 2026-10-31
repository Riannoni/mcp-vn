"""Offline tests: no model, no network, no GPU."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("autonomous_dispatch", HERE/"autonomous_dispatch.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class LocalDispatchTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"lab"/"autonomous"
        case=m.r.load_case("CG-03")
        self.plan=dict(schema="firstshot_one_factor_v1",id="CG03_LEAN_V2",
          case="CG-03",base_case_sha256=m.base_sha("CG-03"),factor="prompt_text",
          new_value=case["prompt"]+" Torso tilted forward at 40 degrees.",
          hypothesis="The model ignores the wall lean because the pose language is insufficiently explicit.",
          falsifier="Original image shows no forward torso angle despite same seed and a stronger lean condition.",
          author_task="R-12")
    def test_idempotent_enqueue_and_no_gpu(self):
        self.assertTrue(m.queue(self.root,self.plan)["enqueued"])
        self.assertFalse(m.queue(self.root,self.plan)["enqueued"])
        with patch.object(m.r,"queue_empty",return_value=False):
            result=m.tick(self.root)
        self.assertEqual(result["status"],"GPU_QUEUE_BUSY_DEFER")
    def test_never_submit_until_explicit_candidate(self):
        with patch.object(m.r,"api",side_effect=AssertionError("GPU called")):
            self.assertEqual(m.tick(self.root)["status"],"NO_APPROVED_WORK")
    def test_invalid_baseline_denied(self):
        self.plan["base_case_sha256"]="0"*64
        with self.assertRaises(ValueError):
            m.queue(self.root,self.plan)
    def test_invalid_authorship_denied(self):
        self.plan["author_task"]="Q-10"
        with self.assertRaises(ValueError):
            m.queue(self.root,self.plan)
    def test_no_factor_change_denied(self):
        self.plan["new_value"]=m.r.load_case("CG-03")["prompt"]
        with self.assertRaises(ValueError):
            m.queue(self.root,self.plan)
    def test_wrong_model_factor_denied(self):
        self.plan["factor"]="checkpoint"
        with self.assertRaises(ValueError):
            m.queue(self.root,self.plan)
    def test_previous_gpu_unknown_never_replayed(self):
        m.setup(self.root)
        (self.root/"running"/"CG03_LEAN_V2.json").write_text("{}")
        with patch.object(m.r,"api",side_effect=AssertionError("duplicate GPU")):
            self.assertEqual(m.tick(self.root)["status"],"STOP_UNKNOWN_PREVIOUS_SUBMISSION")
    def test_pending_pixel_review_blocks_new_gpu(self):
        m.setup(self.root)
        (self.root/"review_pending"/"CG03_LEAN_V2.json").write_text("{}")
        with patch.object(m.r,"api",side_effect=AssertionError("unreviewed render")):
            self.assertEqual(m.tick(self.root)["status"],"WAIT_INDEPENDENT_ORIGINAL_PIXEL_REVIEW")
        self.assertFalse(m.queue(self.root,self.plan)["enqueued"])
    def test_no_private_data_in_user_visible_response(self):
        self.assertNotIn("new_value",m.queue(self.root,self.plan))
    def test_success_moves_running_path_to_review_pending(self):
        """Regression: after pending->running, never rename the stale pending path."""
        import sys
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        self.assertTrue(m.queue(self.root, self.plan)["enqueued"])
        with tempfile.TemporaryDirectory() as home:
            output = Path(home)/".local/share/mcp-vn-comfy/output"
            output.mkdir(parents=True)
            name = "vn_zimage_probe_ab_cg03_lean_v2_exact.png"
            (output/name).write_bytes(b"\x89PNG\r\n\x1a\nfake")
            pid = "11111111-1111-4111-8111-111111111111"
            def fake_api(endpoint, data=None, timeout=8, idempotency_key=None):
                if endpoint == "/prompt":
                    self.assertEqual(idempotency_key, "first-shot-ab:CG03_LEAN_V2")
                    return {"prompt_id": pid}
                if endpoint == "/history/" + pid:
                    return {pid: {"status": {"status_str": "success"},
                                  "outputs": {"node": {"images": [
                                      {"filename": name, "type": "output", "subfolder": ""}]}}}}
                raise AssertionError(endpoint)
            fake_image = MagicMock()
            fake_image.__enter__.return_value.size = (32, 32)
            fake_image.__enter__.return_value.verify.return_value = None
            pil = SimpleNamespace(Image=SimpleNamespace(open=lambda _: fake_image))
            with patch.object(m.r, "queue_empty", return_value=True), \
                 patch.object(m.r, "api", side_effect=fake_api), \
                 patch.object(m.z, "create_graph", return_value={"one": {}}), \
                 patch.object(m.Path, "home", return_value=Path(home)), \
                 patch.dict(sys.modules, {"PIL": pil}):
                result = m.tick(self.root)
        self.assertEqual(result["status"], "GPU_FINISHED_REVIEW_REQUIRED")
        self.assertFalse(list((self.root/"running").glob("*.json")))
        self.assertTrue((self.root/"review_pending"/"CG03_LEAN_V2.json").exists())
        self.assertEqual(json.loads((self.root/"runs"/"CG03_LEAN_V2"/"result.json").read_text())["prompt_id"], pid)

if __name__=="__main__":unittest.main()
