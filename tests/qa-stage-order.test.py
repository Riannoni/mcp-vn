"""Confirm cheap pose geometry gate runs before the slow vision model.

Use an entirely synthetic neutral test image: never touch game saves, GPU
generation or user story content.
"""
import io,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
sys.path.append(str(Path.home()/".local/share/mcp-vn"))
os.environ.setdefault("VN_WORKER_TOKEN","qa-stage-test")
import worker

def sample():
 image=Image.new("RGB",(1216,704),"slategrey")
 memory=io.BytesIO();image.save(memory,format="PNG")
 spec={"composition":"neural_story","resolution":[1216,704],
       "quality":"standard","environment":{"id":"outdoor_courtyard"},
       "characters":[{"name":"Walker","outfit":"jacket","pose":"leaning forward against the wall"}],
       "prompt":"An adult leans forward with both palms on the stone wall, legs straight, rear view"}
 return {"id":"neutral-qa-stage","kind":"scene","prompt":spec["prompt"],
         "spec":spec},memory.getvalue()

class StageOrder(unittest.TestCase):
 def test_bad_geometry_skips_slow_vlm(self):
  job,raw=sample()
  with patch.object(worker,"choose_approved_reference",return_value=({"name":"reference"},"approved")),\
       patch.object(worker,"verify_with_comfy",return_value={"verified":False,"reason":"missing_required_joints"}),\
       patch.object(worker,"request",side_effect=AssertionError("VLM must not run")):
   _,report=worker.assess(job,raw,None)
  self.assertFalse(report["passed"])
  self.assertEqual(report["metrics"]["vlm_skipped_reason"],"pose_geometry_failed")
  self.assertEqual(report["semantic_status"],"failed")
 def test_good_geometry_does_not_override_action_qa(self):
  job,raw=sample()
  def fake_request(base,path,*args,**kwargs):
   self.assertEqual(path,"/judge")
   return {"status":"failed","reasons":["Wall contact cannot be verified"],
           "scene_action_verified":False,"duration_seconds":0.0}
  with patch.object(worker,"choose_approved_reference",return_value=({"name":"reference"},"approved")),\
       patch.object(worker,"verify_with_comfy",return_value={"verified":True,"reason":"geometry_match"}),\
       patch.object(worker,"request",side_effect=fake_request):
   _,report=worker.assess(job,raw,None)
  self.assertFalse(report["passed"])
  self.assertEqual(report["metrics"]["pose_geometry"]["reason"],"geometry_match")
  self.assertNotIn("vlm_skipped_reason",report["metrics"])
  self.assertIn("Wall contact cannot be verified",report["reasons"])

if __name__=="__main__":unittest.main()
