import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from render_invariants import narrator_invariants
from render_retry import retry_plan,permanent_render_failure

class NarratorRenderInvariants(unittest.TestCase):
 def test_background_preserves_environment_for_any_world(self):
  for loc,env in (("Village","open fields"),("Spaceship","orbital station"),
                  ("Desert","dunes and sand")):
   job={"kind":"background","spec":{"location":loc,
       "environment":{"positive":[env],"negative":["forest"]}},
       "prompt":"Narrator-authored cinematic composition."}
   pos,neg=narrator_invariants(job)
   self.assertIn(env,pos);self.assertIn(loc,pos)
   self.assertIn("foreground person",neg)
   self.assertNotIn("Tirren",pos)
 def test_sprite_preserves_variant_and_cutout(self):
  job={"kind":"sprite","character":"Adult Guide",
       "spec":{"variant":{"outfit":"blue jacket","pose":"walking",
                          "emotion":"smile"}}}
  pos,neg=narrator_invariants(job)
  for term in ("exactly one","Full-length","blue jacket","Required pose",
               "plain uniform gray background","canonical"):
   self.assertIn(term,pos)
  self.assertIn("landscape",neg)
 def test_scene_stays_world_agnostic_and_keeps_principals(self):
  job={"kind":"scene","spec":{"characters":[{"name":"Ada"},
      {"name":"Ben"},{"name":"Cam"}],
      "environment":{"positive":["forest"],"negative":["office"]}}}
  pos,neg=narrator_invariants(job)
  for term in ("3 established principal characters","Ada","Ben","Cam","forest"):
   self.assertIn(term,pos)
  self.assertIn("office",neg)

class Recovery(unittest.TestCase):
 def test_only_pose_failures_raise_controlnet_strength(self):
  base={"kind":"scene","attempts":2}
  pose=retry_plan({**base,"error":"CG pose does not match approved DWPose"})
  self.assertEqual(pose["category"],"pose_geometry")
  self.assertEqual(pose["control_strength"],.9)
  self.assertEqual(retry_plan({**base,"attempts":3,"error":"pose geometry"})["control_strength"],1)
  wardrobe=retry_plan({**base,"error":"Wardrobe contradicts current clothes"})
  self.assertEqual(wardrobe["control_strength"],.78)
  self.assertEqual(wardrobe["category"],"wardrobe")
  self.assertNotIn("pose",wardrobe["positive"])
 def test_structural_failures_cannot_retry(self):
  self.assertTrue(permanent_render_failure("Required wall-contact DWPose unavailable: camera"))
  self.assertTrue(permanent_render_failure("Approved DWPose ControlNet could not be applied"))
  self.assertTrue(permanent_render_failure("Incompatible engine contract"))
  self.assertFalse(permanent_render_failure("HTTP Error 429 Too Many Requests"))
  self.assertFalse(permanent_render_failure("CG wardrobe differs"))
if __name__=="__main__":unittest.main()
