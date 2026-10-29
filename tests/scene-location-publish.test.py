import io,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("VN_WORKER_TOKEN","test-only")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from PIL import Image
import worker
class LocationGate(unittest.TestCase):
 def test_positive_vlm_verdict_does_not_override_unknown_location(self):
  image=Image.new("RGB",(512,384),(120,125,128))
  buf=io.BytesIO();image.save(buf,format="PNG")
  spec={"resolution":[512,384],"quality":"standard",
        "composition":"neural_story",
        "environment":{"id":"outdoor_market_square"},
        "characters":[{"name":"Mira"}],"visible_count":1}
  job={"kind":"scene","style":"realistic","attempts":1,
       "prompt":"Mira standing at outdoor market","spec":spec}
  with patch.object(worker,"request",return_value={"status":"passed",
       "caption":"A woman stands on a street.","scene_count_verified":True,
       "scene_location_verified":False,
       "scene_count_confidence":.75,"scene_location_confidence":.16}):
   _,report=worker.assess(job,buf.getvalue(),None)
  self.assertFalse(report["passed"])
  self.assertEqual(report["semantic_status"],"passed")
  self.assertIn("Required CG location not independently verified",
                report["reasons"])
if __name__=="__main__":unittest.main()
