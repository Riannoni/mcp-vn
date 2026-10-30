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
 def _contact_spec(self, contact):
  return {"kind":"scene","composition":"neural_story",
   "characters":[{"name":"Mira"}],
   "visual_contract":{"version":1,"principals":[{"name":"Mira"}],
    "crowd":{"policy":"none"},"contacts":[contact]}}
 def test_missing_blank_or_nonstr_target_fails_closed(self):
  for contact in (
   {"actor":"Mira","kind":"hold"},
   {"actor":"Mira","kind":"hold","target":"  "},
   {"actor":"Mira","kind":"hold","target":True},
   {"actor":"Mira","kind":"hold","target":123}):
   with self.subTest(contact=contact),self.assertRaisesRegex(ValueError,"mandatory contact"):
    scene_contract(self._contact_spec(contact))
 def test_invalid_explicit_target_region_fails_closed(self):
  for region in ([-1,0,.2,.2],[.9,.1,.2,.2],[0,0,0,.2],
                 [0,0,True,.2],[0,0,float("nan"),.2],
                 [0,0,.2],[0,0,.2,.2,.1],"0,0,.2,.2"):
   with self.subTest(region=region),self.assertRaisesRegex(ValueError,"mandatory contact"):
    scene_contract(self._contact_spec(
     {"actor":"Mira","kind":"hold","target":"paper map","target_region":region}))
 def test_valid_contact_with_optional_or_grounded_roi(self):
  for region in (None,[.4,.1,.2,.5]):
   c={"actor":"Mira","kind":"hold","target":"paper map"}
   if region is not None:c["target_region"]=region
   self.assertEqual(scene_contract(self._contact_spec(c))["contacts"],[c])
if __name__=="__main__":unittest.main()
