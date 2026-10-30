import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from qwen_wall_shadow import parse_action_answer
from wall_action_arbitration import may_adjudicate
class QwenWallTest(unittest.TestCase):
 def test_categories_are_not_generic_boolean(self):
  for label in ('HEAD','GROUND','SIDES','PROP','UNCLEAR'):
   self.assertNotEqual(parse_action_answer(label+' (description)')['verdict'],'wall_observed')
  self.assertEqual(parse_action_answer('WALL (both hands against masonry)')['verdict'],'wall_observed')
  self.assertEqual(parse_action_answer('A rock wall is in this image')['verdict'],'unobservable')
 def fixture(self):
  return dict(action_required=True,
   geometry={'verified':True,'wall_contact_corroboration':{'verdict':'plausible'}},
   qwen={'label':'WALL','verdict':'wall_observed'},
   vision={'status':'failed','reasons':['CG action mismatch: ground-supported or kneeling pose'],
           'scene_count_verified':True,'scene_location_verified':True,
           'scene_action_evidence':{'required':True,'forward_lean':True,'both_hands':True,'ground_pose':True}})
 def test_three_source_known_conflict_may_be_adjudicated(self):
  self.assertTrue(may_adjudicate(**self.fixture()))
 def test_other_reasons_and_missing_independence_cannot_pass(self):
  base=self.fixture()
  diffs=[{'action_required':False},{'qwen':{'label':'HEAD','verdict':'not_wall'}},
      {'geometry':{'verified':True,'wall_contact_corroboration':{'verdict':'unobservable'}}},
      {'geometry':{'verified':False}},
      {'vision':{**base['vision'],'scene_location_verified':False}},
      {'vision':{**base['vision'],'scene_count_verified':False}},
      {'vision':{**base['vision'],'reasons':['Invalid wardrobe']}},
      {'vision':{**base['vision'],'reasons':base['vision']['reasons']+['Face drift']}},
      {'vision':{**base['vision'],'scene_action_evidence':{'required':True,'forward_lean':False,'both_hands':True}}}]
  for diff in diffs:
   with self.subTest(diff=diff):self.assertFalse(may_adjudicate(**(base|diff)))
if __name__=='__main__':unittest.main()
