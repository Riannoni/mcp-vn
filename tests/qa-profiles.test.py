import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from qa_profiles import load_profiles
class Profiles(unittest.TestCase):
 def test_all_worlds_share_same_category_ontology(self):
  name,profiles=load_profiles()
  self.assertEqual(len(profiles),3)
  self.assertIn("outdoor_market_square",profiles[name])
  self.assertIn("modern",profiles["modern-v1"]["outdoor_street"])
if __name__=="__main__":unittest.main()
