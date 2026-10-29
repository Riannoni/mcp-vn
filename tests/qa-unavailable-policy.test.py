"""Targeted integration: no sprite can be published with unavailable QA."""
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("VN_WORKER_TOKEN","qa-policy-only-not-real")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from PIL import Image,ImageDraw
import worker
class QAUnavailable(unittest.TestCase):
 def test_sprite_vlm_offline_must_not_pass(self):
  im=Image.new("RGBA",(512,768),(120,100,90,0))
  draw=ImageDraw.Draw(im)
  draw.ellipse((155,20,340,205),fill=(190,150,100,255))
  draw.rectangle((120,195,380,740),fill=(40,110,75,255))
  buf=io.BytesIO();im.save(buf,format="PNG")
  job={"kind":"sprite","style":"realistic","attempts":1,
    "prompt":"One fictional adult wearing a green cloak",
    "spec":{"resolution":[512,768],"quality":"standard",
    "environment":{"id":"unclassified"},
    "variant":{"outfit":"green cloak","pose":"standing","emotion":"neutral"}}}
  with patch.object(worker,"cutout",side_effect=lambda x:x),patch.object(
       worker,"harmonize",side_effect=lambda x,_:x),patch.object(
       worker,"request",return_value={"status":"unavailable","reason":"offline"}):
   _,out=worker.assess(job,buf.getvalue(),None)
  self.assertFalse(out["passed"],out)
  self.assertIn("Semantic QA unavailable"," ".join(out["reasons"]))
  self.assertEqual(out["semantic_status"],"unavailable")
if __name__=="__main__":unittest.main()
