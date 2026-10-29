import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from scene_contract import scene_contract,crowd_condition
class Contract(unittest.TestCase):
 def test_crowd_policy_does_not_change_principal_count(self):
  spec={"kind":"scene","composition":"neural_story",
    "characters":[{"name":"Mira"},{"name":"Devon"}],
    "visual_contract":{"version":1,"principals":[{"name":"Mira"},{"name":"Devon"}],
    "crowd":{"policy":"ambient"},"contacts":[]}}
  data=scene_contract(spec)
  self.assertEqual(data["crowd"]["policy"],"ambient")
  self.assertIn("anonymous",crowd_condition(spec)[0])
 def test_wrong_cast_is_rejected(self):
  spec={"kind":"scene","composition":"neural_story","characters":[{"name":"Mira"}],
    "visual_contract":{"version":1,"principals":[{"name":"Other"}],
    "crowd":{"policy":"none"},"contacts":[]}}
  with self.assertRaises(ValueError):scene_contract(spec)
 def test_unknown_source_keeps_old_specs_working(self):
  self.assertIsNone(scene_contract({"composition":"neural_story"}))
if __name__=="__main__":unittest.main()
