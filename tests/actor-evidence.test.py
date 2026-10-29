import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from actor_evidence import boxes_from_od,principal_spatial_observation
ROIS=[{"name":"Ada","region":[.05,.1,.40,.8]},
      {"name":"Ben","region":[.52,.1,.43,.8]}]
class ActorSpatialEvidence(unittest.TestCase):
 def test_two_named_actor_regions_and_distant_extra(self):
  d={"labels":["woman","man","person","human face"],
      "bboxes":[[50,60,330,470],[600,55,910,475],[920,140,995,260],[10,10,50,55]]}
  v=principal_spatial_observation(ROIS,d,(1000,500))
  self.assertEqual(v["verdict"],"spatially_present")
  self.assertFalse(v["named_identity_verified"])
  self.assertGreaterEqual(v["ambient_detection_count"],1)
 def test_duplicate_detector_labels_dont_count_twice(self):
  raw={"labels":["woman","person"],"bboxes":[[80,40,390,470],[85,45,385,467]]}
  self.assertEqual(len(boxes_from_od(raw,(1000,500))),1)
 def test_one_background_character_cannot_replace_two_named(self):
  raw={"labels":["woman","person"],
       "bboxes":[[55,55,330,440],[90,90,135,130]]}
  v=principal_spatial_observation(ROIS,raw,(1000,500))
  self.assertEqual(v["verdict"],"unobservable")
 def test_missing_regions_remain_unobservable(self):
  v=principal_spatial_observation([{"name":"Ada","region":None}],
     {"labels":["person"],"bboxes":[[0,0,500,500]]},(500,500))
  self.assertEqual(v["reason"],"explicit_actor_regions_required")
if __name__=="__main__":unittest.main()
