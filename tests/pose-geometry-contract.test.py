import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from pose_geometry_contract import inspect_approved_pose

def frame(points):
    arr=[]
    for i in range(18):
        x,y=points.get(i,(i*5,20+i*5))
        confidence=1.0 if i in points else 0.0
        arr.extend((x,y,confidence))
    return [{"people":[{"pose_keypoints_2d":arr}]}]

BASE={
 1:(500,200),2:(510,210),4:(720,220),
 5:(495,215),7:(645,195),8:(290,220),
 9:(330,380),10:(315,570),11:(275,220),
 12:(320,370),13:(308,550),
}
class PoseGeometryTests(unittest.TestCase):
 def test_identical_geometry_passes(self):
  r=inspect_approved_pose(frame(BASE),frame(BASE))
  self.assertTrue(r["verified"],r)
  self.assertEqual(r["angle_deltas_deg"]["torso"],0)

 def test_upright_pose_fails(self):
  upright={
   1:(500,170),2:(530,190),4:(550,400),5:(480,190),
   7:(450,395),8:(505,440),9:(500,590),10:(505,710),
   11:(480,440),12:(470,590),13:(470,710)
  }
  r=inspect_approved_pose(frame(BASE),frame(upright))
  self.assertFalse(r["verified"],r)
  self.assertIn("torso",r["failed_parts"])

 def test_missing_ankles_fail_closed(self):
  r=inspect_approved_pose(frame(BASE),frame({
   k:v for k,v in BASE.items() if k not in (10,13)}))
  self.assertFalse(r["verified"])
  self.assertEqual(r["reason"],"missing_required_joints")

 def test_multiple_people_fail(self):
  r=inspect_approved_pose(frame(BASE),[{"people":[{"pose_keypoints_2d":[0]*54},
                              {"pose_keypoints_2d":[0]*54}]}])
  self.assertFalse(r["verified"])
  self.assertEqual(r["reason"],"expected_one_detected_person")

if __name__=="__main__":unittest.main()
