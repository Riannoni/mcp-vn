import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from contact_geometry import inspect_contact_region

def pose(r=(.25,.25),l=(.26,.26),right_conf=1,left_conf=1,extra=False):
 k=[0.,0.,0.]*18
 for n,(pos,c) in enumerate(((r,right_conf),(l,left_conf))):
  idx=(4,7)[n];k[idx*3:idx*3+3]=[pos[0]*1000,pos[1]*1000,c]
 raw={"canvas_width":1000,"canvas_height":1000,
      "people":[{"pose_keypoints_2d":k}]}
 if extra:raw["people"].append({"pose_keypoints_2d":k})
 return raw
class ContactGeometry(unittest.TestCase):
 def setUp(self):self.contact={"target_region":[.20,.20,.15,.25]}
 def test_visibly_wrong_contact_is_a_confident_violation(self):
  out=inspect_contact_region(pose((.85,.85),(.88,.80)),self.contact)
  self.assertEqual(out["verdict"],"violated")
 def test_near_object_does_not_prove_touch(self):
  out=inspect_contact_region(pose(),self.contact)
  self.assertEqual(out["verdict"],"plausible")
 def test_one_hidden_hand_is_unknown(self):
  out=inspect_contact_region(pose(right_conf=.1),self.contact)
  self.assertEqual(out["verdict"],"unobservable")
 def test_ambiguous_people_or_object_is_unknown(self):
  self.assertEqual(inspect_contact_region(pose(extra=True),self.contact)["verdict"],"unobservable")
  self.assertEqual(inspect_contact_region(pose(),{})["verdict"],"unobservable")
if __name__=="__main__":unittest.main()
