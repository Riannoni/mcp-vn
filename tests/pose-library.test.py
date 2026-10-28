import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from pose_library import POSES,point_list,validate_pose,pose_json,select_story_pose
class Tests(unittest.TestCase):
 def test_catalog(self):
  self.assertGreaterEqual(len(POSES),24)
  self.assertEqual(len(set(tuple(point_list(k)) for k in POSES)),len(POSES))
  self.assertTrue(all(validate_pose(k) for k in POSES))
 def test_metadata(self):
  doc=pose_json("brace_wall_rear",1216,704)
  self.assertEqual(len(doc["people"][0]["pose_keypoints_2d"]),54)
  self.assertEqual(doc["canvas_width"],1216)
 def test_selection(self):
  self.assertEqual(select_story_pose("Both palms on stone wall, leaning forward, rear view"),"brace_wall_rear")
  self.assertEqual(select_story_pose("Standing near the rear door"),"")
if __name__=="__main__":unittest.main()
