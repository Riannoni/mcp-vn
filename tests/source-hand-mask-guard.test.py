import unittest,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from source_hand_mask_guard import check_stale_hand_coverage
class SourceHandGuard(unittest.TestCase):
 def pose(self):
  people={}
  for side,x in [('hand_left_keypoints_2d',110),('hand_right_keypoints_2d',185)]:
   v=[]
   for i in range(21):v.extend([x+(i%3),150+i%7,1.0])
   people[side]=v
  return dict(canvas_width=300,canvas_height=220,people=[people])
 def test_old_hands_locked_rejects(self):
  x=Image.new('L',(300,220),0)
  self.assertEqual(check_stale_hand_coverage(self.pose(),0,x)['verdict'],'violated')
 def test_old_hands_editable_allows_only_preflight(self):
  im=Image.new('L',(300,220),0)
  ImageDraw.Draw(im).rectangle((90,130,215,180),fill=255)
  self.assertEqual(check_stale_hand_coverage(self.pose(),0,im)['verdict'],'covered_for_replacement')
 def test_one_hand_stale_rejects(self):
  im=Image.new('L',(300,220),0)
  ImageDraw.Draw(im).rectangle((90,130,139,180),fill=255)
  self.assertEqual(check_stale_hand_coverage(self.pose(),0,im)['verdict'],'violated')
 def test_ambiguity_cannot_pass(self):
  self.assertEqual(check_stale_hand_coverage({},0,Image.new('L',(300,220),255))['verdict'],'unobservable')
if __name__=='__main__':unittest.main()
