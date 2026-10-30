import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from atomic_visual_evidence import atomic_prompt_pair,atomic_decision,required_atomic_items,atomic_report_matches_claims
from scene_contract import scene_contract

class AtomicEvidenceTest(unittest.TestCase):
 def test_known_positive_negative_fixture_scores(self):
  # Local human-audited benchmark: original SDXL fruit basket <0.29,
  # first Z-Image map 0.913 (same CLIP object contrast); not general accuracy.
  obj={'kind':'object','description':'unfolded paper map'}
  self.assertIsNotNone(atomic_prompt_pair(obj,'outdoor_market_square'))
  self.assertEqual(atomic_decision(obj,.913),'verified')
  self.assertEqual(atomic_decision(obj,.289),'violated')
  self.assertEqual(atomic_decision(obj,.55),'unobservable')
 def test_landmark_and_relation_cannot_auto_pass_from_caption(self):
  arch={'kind':'landmark','description':'stone archway'}
  self.assertIsNotNone(atomic_prompt_pair(arch,'outdoor_market_square'))
  self.assertIsNone(atomic_prompt_pair(arch,'unclassified'))
  self.assertEqual(atomic_decision(arch,.859),'verified')
  self.assertEqual(atomic_decision(arch,.24),'violated')
  rel={'kind':'relation','description':'hands touching wall','actor':'Ada','action':'both palms braced'}
  self.assertIsNone(atomic_prompt_pair(rel,'outdoor_market_square'))
  self.assertEqual(atomic_decision(rel,.99),'unobservable')
 def test_required_checks_are_explicit_not_guess_from_story_prompt(self):
  self.assertEqual(required_atomic_items({'prompt':'A woman with a map'}),[])
 def test_incomplete_or_forged_positive_vision_payload_cannot_verify_scene(self):
  wanted=[{'kind':'object','description':'paper map','actor':'Ada'},
          {'kind':'landmark','description':'stone archway'}]
  valid=[{'index':0,'kind':'object','description':'paper map','actor':'Ada','verdict':'verified'},
         {'index':1,'kind':'landmark','description':'stone archway','actor':'','verdict':'verified'}]
  self.assertTrue(atomic_report_matches_claims(wanted,valid))
  self.assertFalse(atomic_report_matches_claims(wanted,valid[:1]))
  self.assertFalse(atomic_report_matches_claims(wanted,valid[::-1]))
  self.assertFalse(atomic_report_matches_claims(wanted,[dict(x,description='fake') for x in valid]))

 def test_scene_contract_rejects_unknown_cast_claims(self):
  spec={'kind':'scene','composition':'neural_story','characters':[{'name':'Ada'}],
    'visual_contract':{'version':1,'principals':[{'name':'Ada'}],
    'crowd':{'policy':'none'},'contacts':[],
    'required_visuals':[{'kind':'object','description':'paper map','actor':'Unknown'}]}}
  with self.assertRaisesRegex(ValueError,'Unknown actor'):scene_contract(spec)

if __name__=='__main__':unittest.main()
