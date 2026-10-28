import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from scene_caption_contract import scene_caption_conflicts

class SceneCaptionContractTest(unittest.TestCase):
 def test_exact_bad_cg_caption_is_rejected(self):
  caption=("One adult is standing with her back to us while another stands facing "
           "forward. The woman has long hair tied up in a bun. She's wearing a blue top")
  problems=scene_caption_conflicts([{"name":"Mira","outfit":"unclothed"}],caption)
  self.assertEqual(len(problems),2)
 def test_consistent_caption_is_not_rejected(self):
  self.assertEqual(scene_caption_conflicts(
      [{"name":"Mira","outfit":"green coat"}],
      "One adult woman wearing a green coat in a market street."),[])
 def test_two_person_scene_not_falsely_rejected(self):
  self.assertEqual(scene_caption_conflicts(
      [{"name":"Mira","outfit":"traveler clothes"},
       {"name":"Lia","outfit":"robe"}],
      "Two people face one another in a courtyard."),[])

if __name__=="__main__":
 unittest.main()
