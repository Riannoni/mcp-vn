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
if __name__=="__main__":unittest.main()
