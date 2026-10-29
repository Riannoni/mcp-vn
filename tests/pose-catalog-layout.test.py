import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from pose_contracts import POSE_CONTRACTS,pose_contract
from actor_layout import region_for_actor,assert_cast_supported,MAX_CG_FACE_ANCHORS
from scene_constraints import scene_constraints

class CatalogLayoutTests(unittest.TestCase):
 def test_popular_pose_catalog_is_complete_and_typed(self):
  self.assertGreaterEqual(len(POSE_CONTRACTS),30)
  for key,record in POSE_CONTRACTS.items():
   self.assertEqual(len(record),3,key)
   self.assertTrue(all(record),key)
   self.assertEqual(pose_contract(key)["status"],"text_contract_only")
   self.assertFalse(pose_contract(key)["approved_control"])
 def test_freeform_pose_never_auto_approves_control(self):
  self.assertIsNone(pose_contract("leaning toward a wall and doing something"))
 def test_one_to_four_main_characters(self):
  for count in (1,2,3,4):
   self.assertEqual(assert_cast_supported([{"name":str(i)} for i in range(count)]),count)
   regions=[region_for_actor(i,count) for i in range(count)]
   self.assertTrue(all(0<=x0<x1<=1 and 0<=y0<y1<=1 for x0,y0,x1,y1 in regions))
  with self.assertRaisesRegex(ValueError,"5 main characters"):
   assert_cast_supported([{"name":str(i)} for i in range(5)])
 def test_actor_specific_regions_and_invalid_shapes(self):
  self.assertEqual(region_for_actor(1,3,[.1,.2,.5,.6]),(.1,.2,.6,.8))
  with self.assertRaises(ValueError):
   region_for_actor(1,3,[.9,.2,.3,.6])
 def test_individual_actor_pose_descriptions(self):
  spec={"composition":"neural_story",
        "characters":[{"name":"Ada","outfit":"coat","pose":"stand_point"},
                      {"name":"Ben","outfit":"suit","pose":"kneel_one"},
                      {"name":"Cam","outfit":"shirt","pose":"sit_chair_side"}]}
  pos,neg=scene_constraints(spec,"Three people in a room")
  self.assertIn("Actor Ada physical pose:",pos)
  self.assertIn("Actor Ben physical pose:",pos)
  self.assertIn("Actor Cam physical pose:",pos)
  self.assertNotIn("not kneeling",neg)
 def test_bystanders_do_not_require_anchor_region(self):
  cast=[{"name":"Ada"},{"name":"Ben"},{"name":"Cam"}]
  self.assertEqual(assert_cast_supported(cast),3)
if __name__=="__main__":unittest.main()
