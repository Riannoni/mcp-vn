import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from interaction_blocking import validate_bimanual_prop,draft_pose_from_front_template,BlockingError
class BimanualBlocking(unittest.TestCase):
 def good(self):
  return dict(version=1,actor_id='actor-A',object_id='paper_map',view='front',
   object_region=dict(x0=.38,y0=.37,x1=.64,y1=.66),
   right_hand=dict(x=.39,y=.5),left_hand=dict(x=.63,y=.5))
 def test_typed_front_plan_valid(self):
  plan=validate_bimanual_prop(self.good(),['actor-A'])
  self.assertTrue(plan['status'].startswith('draft'))
 def test_incomplete_or_wrong_interactions_fail_closed(self):
  cases=[{'right_hand':{'x':.45,'y':.86}},
   {'left_hand':{'x':.39,'y':.5}}, {'view':'rear'},
   {'actor_id':'not-stated'}, {'object_region':{'x0':0,'y0':0,'x1':1,'y1':1}}]
  for fields in cases:
   with self.subTest(fields=fields):
    with self.assertRaises(BlockingError):validate_bimanual_prop(self.good()|fields,['actor-A'])
 def test_draft_guide_targets_real_wrist_indices(self):
  original=dict(canvas_width=1000,canvas_height=600,
        people=[{'pose_keypoints_2d':[0.0,0.0,1.0]*18}])
  # Shoulders exist in the template; exact wrist outputs come from contract.
  plan=validate_bimanual_prop(self.good(),['actor-A'])
  out=draft_pose_from_front_template(original,plan)
  pts=out['people'][0]['pose_keypoints_2d']
  self.assertEqual(pts[4*3:4*3+2],[390,300])
  self.assertEqual(pts[7*3:7*3+2],[630,300])
  self.assertTrue(out['status'].startswith('draft'))
  self.assertEqual(len(out['interaction_contract_hash']),64)
if __name__=='__main__':unittest.main()
