"""End-to-end CPU-worker panel gate: no VLM request on a tiled CGI."""
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw

os.environ.setdefault("VN_WORKER_TOKEN","test-only-panel-gate")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
import worker

class WorkerPanelGate(unittest.TestCase):
 def test_tiled_scene_rejected_before_vlm(self):
  tile=Image.new("RGB",(256,192),(40,50,70))
  d=ImageDraw.Draw(tile)
  pixels=tile.load()
  for y in range(192):
   for x in range(256):
    pixels[x,y]=(x,y,120)
  d.ellipse((45,40,140,160),fill=(240,180,40))
  d.rectangle((175,15,230,185),fill=(100,220,70))
  image=Image.new("RGB",(512,384))
  for x in (0,256):
   for y in (0,192):image.paste(tile,(x,y))
  raw=io.BytesIO();image.save(raw,format="PNG")
  job={"kind":"scene","prompt":"Two people standing in market",
       "spec":{"composition":"neural_story","resolution":[512,384],
       "environment":{"id":"outdoor_market_square"},
       "characters":[{"name":"First"},{"name":"Second"}],"visible_count":2}}
  with patch.object(worker,"request",side_effect=AssertionError("No VLM needed")) as req:
   _,report=worker.assess(job,raw.getvalue(),None)
  self.assertFalse(report["passed"])
  self.assertEqual(report["semantic_status"],"failed")
  self.assertTrue(report["metrics"]["panel_collage_detected"])
  self.assertEqual(report["metrics"]["vlm_skipped_reason"],"panel_layout_failed")
  self.assertIn("multi-panel collage"," ".join(report["reasons"]))
  req.assert_not_called()

if __name__=="__main__":unittest.main()
