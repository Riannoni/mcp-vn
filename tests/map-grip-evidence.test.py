import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from map_grip_evidence import evaluate
class MapGripEvidence(unittest.TestCase):
 def pose(self,left=(.4,.45),right=(.66,.45)):
  actor={}
  for side,(x,y) in zip(('hand_left_keypoints_2d','hand_right_keypoints_2d'),(left,right)):
   p=[]
   for i in range(21):p.extend([x*1000,y*600,1.0])
   actor[side]=p
  return {'canvas_width':1000,'canvas_height':600,'people':[actor]}
 def check(self,left=(.4,.45),right=(.66,.45),caption='Woman holding a paper map in both hands',boxes=[[395,190,670,340]]):
  return evaluate(self.pose(left,right),0,boxes,(1000,600),caption)['verdict']
 def test_both_hands_on_distinct_edges_only_plausible(self):
  self.assertEqual(self.check(),'plausible')
  self.assertNotEqual(self.check(),'verified')
 def test_hand_below_map_not_accepted(self):
  self.assertEqual(self.check(left=(.4,.69)),'unobservable')
 def test_vague_caption_or_wrong_box_not_accepted(self):
  self.assertEqual(self.check(caption='Woman next to a map'),'unobservable')
  self.assertEqual(self.check(boxes=[[0,0,999,599]]),'unobservable')
 def test_missing_person_not_accepted(self):
  self.assertEqual(evaluate(self.pose(),12,[[395,190,670,340]],(1000,600),'holding map')['verdict'],'unobservable')
if __name__=='__main__':unittest.main()
