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
  self.assertEqual(r["reason"],"no_complete_foreground_person")

def shifted_person(scale=1.0,xoffset=0,yoffset=0):
 points={i:(x*scale+xoffset,y*scale+yoffset) for i,(x,y) in BASE.items()}
 return frame(points)[0]["people"][0]

class PrincipalSelectionTests(unittest.TestCase):
 def test_many_tiny_background_detections_do_not_hide_principal(self):
  principal=shifted_person()
  tiny=shifted_person(.12,-5,3)
  people=[principal]+[tiny]*8
  result=inspect_approved_pose(frame(BASE),[{"people":people}])
  self.assertTrue(result["verified"],result)
  self.assertEqual(result["principal_index"],0)
  self.assertEqual(result["candidate_people"],9)

 def test_roi_selects_named_actor_among_large_bystanders(self):
  principal=shifted_person(.8,50,20)
  other=shifted_person(.9,700,0)
  actual=[{"canvas_width":1600,"canvas_height":800,"people":[other,principal]}]
  verdict=inspect_approved_pose(frame(BASE),actual,actor_region=[.05,.02,.40,.95])
  self.assertTrue(verdict["verified"],verdict)
  self.assertEqual(verdict["principal_index"],1)
  self.assertTrue(verdict["principal_selected_by_roi"])

 def test_roi_with_two_possible_actors_is_unobservable(self):
  figures=[shifted_person(),shifted_person(.9,30,10)]
  actual=[{"canvas_width":1600,"canvas_height":800,"people":figures}]
  verdict=inspect_approved_pose(frame(BASE),actual,actor_region=[0,0,.60,1])
  self.assertEqual(verdict["reason"],"ambiguous_principal_roi")
  self.assertFalse(verdict["verified"])

 def test_second_similarly_large_foreground_figure_is_ambiguous(self):
  people=[shifted_person(),shifted_person(.9,30,10)]
  result=inspect_approved_pose(frame(BASE),[{"people":people}])
  self.assertFalse(result["verified"])
  self.assertEqual(result["reason"],"ambiguous_foreground_people")

 def test_wrong_main_pose_cannot_be_excused_by_matching_tiny_bystander(self):
  standing={1:(500,170),2:(530,190),4:(550,400),5:(480,190),
   7:(450,395),8:(505,440),9:(500,590),10:(505,710),
   11:(480,440),12:(470,590),13:(470,710)}
  main=frame(standing)[0]["people"][0]
  bystander=shifted_person(.12)
  result=inspect_approved_pose(frame(BASE),
       [{"people":[bystander,main]}])
  self.assertFalse(result["verified"])
  self.assertIn("torso",result["failed_parts"])
  self.assertEqual(result["principal_index"],1)

if __name__=="__main__":unittest.main()
