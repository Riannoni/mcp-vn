import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from identity_observation import face_observability,face_similarity_decision
class Identity(unittest.TestCase):
 def test_rear_no_face_claim(self):
  x=face_observability({"variant":{"pose":"standing from behind, face hidden"}})
  self.assertEqual(x["verdict"],"unobservable")
 def test_rear_request_does_not_excuse_front_facing_mismatch(self):
  x=face_similarity_decision({"variant":{"pose":"from behind"}},.62,
    "The woman is looking directly at the camera.")
  self.assertEqual(x["verdict"],"violated")
 def test_rear_caption_can_be_unobservable_not_verified(self):
  x=face_similarity_decision({"variant":{"pose":"from behind"}},.62,
    "A woman is shown from behind; her face is not visible.")
  self.assertEqual(x["verdict"],"unobservable")
 def test_front_does_not_prove_identity(self):
  x=face_observability({"variant":{"pose":"standing front three-quarter"}})
  self.assertEqual(x["verdict"],"potentially_visible")
if __name__=="__main__":unittest.main()
