import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from atomic_prop_gate import evaluate
class AtomicPropGate(unittest.TestCase):
 def fixture(self):
  v=[0.]*54
  v[6:9]=[400,200,.99];v[15:18]=[500,201,.99]
  req={'actor_id':'actor_1','target_id':'paper_map','contact_kind':'hold_both_hands','view':'front','same_depth':True,'max_width_to_shoulders':1.}
  obs={'actor_id':'actor_1','target_id':'paper_map','object_match':'verified','object_method':'florence_grounding','pose_frame':{'canvas_width':1000,'canvas_height':600,'people':[{'pose_keypoints_2d':v}]},'principal_index':0,'object_boxes':[[420,220,490,300]],'detector_size':(1000,600),'contact_verdict':'both_touch','contact_method':'independent_atomic_vlm'}
  return req,obs
 def test_positive_only_plausible_never_full_verified(self):
  r,o=self.fixture();v=evaluate(r,o)
  self.assertEqual(v['status'],'plausible_pending_scene_qa');self.assertFalse(v['can_publish'])
  self.assertEqual(v['evidence']['projected_size']['projected_ratio'],.7)
 def test_map_replaced_with_basket_is_hard_rejected(self):
  r,o=self.fixture();o['object_match']='violated'
  self.assertIn('mandatory_required_object_mismatch',evaluate(r,o)['reasons'])
 def test_missing_object_is_unobservable_not_pass(self):
  r,o=self.fixture();o['object_boxes']=[]
  self.assertIn('mandatory_object_scale_unobservable',evaluate(r,o)['reasons'])
 def test_oversized_prop_is_rejected_even_when_atomic_vlm_says_touch(self):
  r,o=self.fixture();o['object_boxes']=[[360,210,550,350]]
  self.assertIn('required_object_exceeds_typed_projected_size',evaluate(r,o)['reasons'])
 def test_one_hand_or_proximity_not_contact(self):
  r,o=self.fixture();o['contact_verdict']='one_touch'
  self.assertIn('mandatory_two_hand_contact_violated',evaluate(r,o)['reasons'])
  o['contact_verdict']='both_touch';o['contact_method']='dwpose_proximity'
  self.assertIn('physical_contact_provenance_missing',evaluate(r,o)['reasons'])
 def test_missing_provenance_cannot_verify(self):
  r,o=self.fixture();o.pop('object_method')
  self.assertIn('object_grounding_provenance_missing',evaluate(r,o)['reasons'])
 def test_wrong_actor_or_target_no_accept(self):
  r,o=self.fixture();o['actor_id']='different'
  self.assertIn('object_or_actor_attribution_mismatch',evaluate(r,o)['reasons'])
 def test_wrong_camera_depth_and_missing_pose(self):
  r,o=self.fixture();r['view']='back'
  self.assertIn('mandatory_object_scale_unobservable',evaluate(r,o)['reasons'])
  r['view']='front';o['pose_frame']=None
  self.assertIn('mandatory_object_scale_unobservable',evaluate(r,o)['reasons'])
 def test_invalid_typed_contract_fails_closed(self):
  for x in (None,True,-1,0,float('nan')):
   r,o=self.fixture();r['max_width_to_shoulders']=x
   self.assertIn('typed_prop_contract_invalid',evaluate(r,o)['reasons'])
 def test_unobservable_contact_cannot_publish(self):
  r,o=self.fixture();o['contact_verdict']='unobservable'
  self.assertIn('mandatory_two_hand_contact_unobservable',evaluate(r,o)['reasons'])
if __name__=='__main__':unittest.main()
