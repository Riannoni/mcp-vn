#!/usr/bin/env python3
"""Deterministic regression checks for CLIP evidence thresholds."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from scene_qa_rules import principal_count_evidence,scene_location_evidence

GOOD_TWO={
 "solo_portrait":.039,"solo_person":.120,"solo_woman":.050,
 "pair_people":.240,"pair_interaction":.160,"pair_mixed":.0919,
 "group_three":.180,"group_many":.071,"no_people":.0481
}
BAD_ONE={
 "solo_portrait":.240,"solo_person":.127,"solo_woman":.0299,
 "pair_people":.140,"pair_interaction":.118,"pair_mixed":.0748,
 "group_three":.106,"group_many":.061,"no_people":.1043
}
MARKET={"outdoor_market_square":.448,"outdoor_street":.309,
 "outdoor_forest":.011,"outdoor_courtyard":.119}
WRONG_FOREST={"outdoor_market_square":.044,"outdoor_street":.083,
 "outdoor_forest":.468,"outdoor_courtyard":.047}

class SceneEvidenceTest(unittest.TestCase):
 def test_strong_indoor_conflict_rejected_for_market(self):
  scores={"outdoor_market_square":.128,"outdoor_street":.134,
    "outdoor_courtyard":.057,"outdoor_forest":.02,
    "indoor_room":.116,"indoor_tavern":.235,"underground_cave":.309}
  ok,reasons,_=scene_location_evidence("outdoor_market_square",scores)
  self.assertFalse(ok)
  self.assertIn("indoor evidence",reasons[0])
 def test_ambiguous_market_never_claims_verified(self):
  scores={"outdoor_market_square":.17,"outdoor_street":.22,
    "outdoor_courtyard":.06,"outdoor_forest":.10,
    "indoor_room":.08,"indoor_tavern":.24,"underground_cave":.13}
  ok,reasons,_=scene_location_evidence("outdoor_market_square",scores)
  self.assertFalse(ok)
  self.assertEqual(reasons,[])
 def test_correct_two_person_market_frame_is_accepted(self):
  ok,reasons,confidence=principal_count_evidence(2,GOOD_TWO)
  self.assertTrue(ok,reasons)
  self.assertGreater(confidence,.4)
  ok,reasons,_=scene_location_evidence("outdoor_market_square",MARKET)
  self.assertTrue(ok,reasons)
 def test_one_person_portrait_cannot_pass_as_two_people(self):
  ok,reasons,_=principal_count_evidence(2,BAD_ONE)
  self.assertFalse(ok)
  self.assertIn("cannot",reasons[0])
 def test_forest_is_rejected_for_market_location_even_if_outdoors(self):
  ok,reasons,_=scene_location_evidence("outdoor_market_square",WRONG_FOREST)
  self.assertFalse(ok)
  self.assertIn("forest",reasons[0])
 def test_unknown_location_is_not_promoted_to_verified_reference(self):
  ok,reasons,_=scene_location_evidence("unclassified",{})
  self.assertFalse(ok)
  self.assertEqual(reasons,[])
 def test_no_expected_cast_cannot_be_scene_verified(self):
  ok,reasons,_=principal_count_evidence(0,{})
  self.assertFalse(ok)
  self.assertTrue(reasons)

if __name__=="__main__":
 unittest.main()
