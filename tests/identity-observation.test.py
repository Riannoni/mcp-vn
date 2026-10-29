import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from identity_observation import face_observability
class Identity(unittest.TestCase):
 def test_rear_no_face_claim(self):
  x=face_observability({"variant":{"pose":"standing from behind, face hidden"}})
  self.assertEqual(x["verdict"],"unobservable")
 def test_front_does_not_prove_identity(self):
  x=face_observability({"variant":{"pose":"standing front three-quarter"}})
  self.assertEqual(x["verdict"],"potentially_visible")
if __name__=="__main__":unittest.main()
