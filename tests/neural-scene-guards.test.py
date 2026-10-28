import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from neural_scene_guards import neural_scene_guards


class NeuralSceneGuardsTests(unittest.TestCase):
 def test_one_principal_and_market_fixes_real_report(self):
  spec={"composition":"neural_story",
   "characters":[{"name":"Mira","appearance":"adult with clock-shaped shoulder mark"}],
   "environment":{"id":"outdoor_market_square"}}
  pos,neg,source=neural_scene_guards(
      spec,3,"Expected 1 principal figures cannot be verified",
      "Mira has a silver clock-like mark; rear three-quarter viewpoint")
  self.assertIn("one adult person only",pos)
  self.assertIn("one human body",pos)
  self.assertIn("SOLO",pos)
  self.assertNotIn("daylight",pos)
  self.assertIn("open-air outdoor market square",pos)
  self.assertIn("small flat silver tattoo".upper(),pos.upper())
  self.assertNotIn("No physical camera",pos)
  self.assertIn("2girls",neg)
  self.assertIn("camera body",neg)
  self.assertIn("wall-mounted clock",neg)
  self.assertEqual(source,"neural_scene_guards_v1")

 def test_two_person_shot_does_not_force_solo(self):
  positive,negative,_=neural_scene_guards({
   "composition":"neural_story",
   "characters":[{"name":"Mira"},{"name":"Max"}],
   "environment":{"id":"outdoor_street"}})
  self.assertIn("Exactly 2 separate established principal characters",positive)
  self.assertNotIn("SOLO FEMALE SUBJECT",positive)
  self.assertNotIn("2girls",negative)

 def test_requested_physical_props_are_respected(self):
  p,n,_=neural_scene_guards({
   "composition":"neural_story",
   "characters":[{"name":"Mira"}]},
   subject="Mira is a photographer holding a camera under a tower clock")
  self.assertNotIn("camera body",n)
  self.assertNotIn("wall-mounted clock",n)

 def test_layered_CG_is_untouched(self):
  self.assertEqual(neural_scene_guards({
   "composition":"anchored_composite","characters":[{"name":"Mira"}]}),("","",""))


if __name__=="__main__":
 unittest.main()
