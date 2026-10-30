import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from scene_constraints import scene_constraints

class SceneConstraintsTest(unittest.TestCase):
    def test_story_state_clothing_and_wall_contact_are_prioritized(self):
        spec={"composition":"neural_story","characters":[
          {"name":"Mira","outfit":"unclothed","pose":"leaning"}
        ]}
        positive,negative=scene_constraints(
          spec,"A single adult leans forward against a stone wall with both palms.")
        self.assertIn("CURRENT WARDROBE CONTRACT",positive)
        self.assertIn("facial identity ONLY",positive)
        self.assertIn("VERTICAL wall",positive)
        self.assertIn("feet and hands on the wall",positive)
        self.assertIn("worn clothing",negative)
        self.assertIn("lying",negative)

    def test_outfit_change_does_not_reuse_canonical_cloak(self):
        spec={"composition":"neural_story","characters":[
          {"name":"Mira","outfit":"blue travel jacket","pose":"walking"}
        ]}
        pos,neg=scene_constraints(spec,"One person walking down a road.")
        self.assertIn("blue travel jacket",pos)
        self.assertIn("old character reference",pos)
        self.assertNotIn("all visible characters wear no garments",pos)
        self.assertNotIn("worn clothing",neg)

    def test_mixed_cast_does_not_apply_global_wardrobe_exclusion(self):
        spec={"composition":"neural_story","characters":[
          {"name":"One","outfit":"unclothed","pose":"standing"},
          {"name":"Two","outfit":"robe","pose":"standing"}
        ]}
        positive,negative=scene_constraints(spec,"Two people in a room.")
        self.assertIn("CURRENT WARDROBE CONTRACT for One",positive)
        self.assertIn("CURRENT WARDROBE CONTRACT for Two",positive)
        self.assertIn("no garments worn",positive)
        self.assertIn("robe",positive)
        self.assertNotIn("worn clothing",negative)

    def test_mandatory_object_prompt_is_not_silently_discarded(self):
        spec={"composition":"neural_story","characters":[
           {"name":"Ada","outfit":"blue jacket","pose":"standing"}],
           "visual_contract":{"required_visuals":[
             {"kind":"object","description":"folded paper map","actor":"Ada","action":"studying"},
             {"kind":"landmark","description":"stone archway"}]}}
        pos,_=scene_constraints(spec,"a traveler at a market")
        self.assertIn("MANDATORY VISUAL OBJECT",pos)
        self.assertIn("folded paper map",pos)
        self.assertIn("stone archway",pos)

    def test_other_compositions_are_untouched(self):
        self.assertEqual(scene_constraints({
          "composition":"anchored_composite",
          "characters":[{"outfit":"unclothed"}]
        },"leans on wall"),("",""))

if __name__=="__main__":
 unittest.main()
