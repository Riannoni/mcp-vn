import sys
import unittest
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from panel_guard import detect_four_panel_collage
from render_retry import retry_plan

class PanelGuard(unittest.TestCase):
 def test_synthetic_repeated_panels(self):
  # Four near-duplicate views of same two shapes with distinct panel seams.
  import random
  rng=random.Random(304)
  tile=Image.new("RGB",(256,192),(190,167,145))
  d=ImageDraw.Draw(tile)
  for _ in range(45):
   x=rng.randrange(0,240); y=rng.randrange(0,175)
   d.rectangle((x,y,x+10,y+12),fill=(rng.randrange(10,180),80,120))
  # A clear repeated top-to-bottom jump ensures both panel seams.
  for row in range(192):
   d.line((0,row,255,row),fill=(row,90,50),width=1) if row%5==0 else None
  sheet=Image.new("RGB",(512,384),(50,50,50))
  for x in (0,256):
   for y in (0,192):sheet.paste(tile,(x,y))
  report=detect_four_panel_collage(sheet)
  self.assertTrue(report["detected"],report)
 def test_continuous_image_not_rejected(self):
  im=Image.new("RGB",(512,384))
  p=im.load()
  for y in range(384):
   for x in range(512):p[x,y]=(int(x*.4),int(y*.5),100)
  self.assertFalse(detect_four_panel_collage(im)["detected"])
 def test_non_repeated_grid_not_rejected(self):
  # A window-like cross should not automatically be treated as four scenes.
  import random
  rng=random.Random(929)
  im=Image.new("RGB",(512,384),(32,32,32))
  d=ImageDraw.Draw(im)
  for i in range(4):
   x=(i%2)*256
   y=(i//2)*192
   color=(i*40+25,120,180)
   d.rectangle((x,y,x+253,y+189),fill=color)
   for j in range(20):
    px=x+rng.randint(3,230);py=y+rng.randint(3,167)
    d.ellipse((px,py,px+12,py+12),fill=(rng.randint(0,255),40,60))
  self.assertFalse(detect_four_panel_collage(im)["detected"])
 def test_retry_targets_tiling(self):
  p=retry_plan({"kind":"scene","attempts":2,
                "error":"CG multi-panel collage: expected one continuous scene"})
  self.assertEqual(p["category"],"panel_layout")
  self.assertIn("split screen",p["negative"])
  self.assertEqual(p["control_strength"],.78)
if __name__=="__main__":unittest.main()
