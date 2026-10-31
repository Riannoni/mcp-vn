import sys, unittest, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from scene_action_contract import wall_brace_required,check_wall_action

class WallActionContractTests(unittest.TestCase):
    SPEC={
        "composition":"neural_story",
        "characters":[{"name":"Mira","pose":"leaning"}],
        "prompt":"One adult leans forward with both palms on the inner stone wall, legs straight",
    }
    def test_actual_bad_vlm_caption_is_rejected(self):
        observed="A woman with red hair is standing on a stone path next to a building. She has her legs crossed."
        ok,reasons,ev=check_wall_action(observed,self.SPEC)
        self.assertFalse(ok)
        self.assertTrue(reasons)
        self.assertFalse(ev["wall_touch"])

    def test_clear_two_hand_wall_brace_passes(self):
        observed=("An adult leans forward toward a vertical masonry wall, "
                  "pressing both palms against the wall, standing on both feet.")
        ok,reasons,ev=check_wall_action(observed,self.SPEC)
        self.assertTrue(ok,(reasons,ev))
        self.assertEqual(reasons,[])

    def test_generic_wall_proximity_is_not_contact(self):
        ok,reasons,ev=check_wall_action(
            "A woman stands next to the wall with both hands by her sides.",self.SPEC)
        self.assertFalse(ok)
        self.assertFalse(ev["wall_touch"])

    def test_ground_pose_fails_even_with_wall_mentioned(self):
        ok,reasons,ev=check_wall_action(
            "A woman is lying on the paved street, beside the stone wall.",self.SPEC)
        self.assertFalse(ok)
        self.assertTrue(ev["ground_pose"])

    def test_wall_contact_with_feet_on_ground_not_false_rejected(self):
        observed=("The woman bends forward at her hips, both hands pressed against "
                  "the stone wall. Her feet are planted on cobblestone ground.")
        ok,reasons,ev=check_wall_action(observed,self.SPEC)
        self.assertTrue(ok,(reasons,ev))
        self.assertFalse(ev["ground_pose"])

    def test_ambiguous_action_does_not_pass(self):
        observed=("One woman is leaning forward next to a wall. "
                  "Her hands are not visible so contact is unclear.")
        ok,reasons,ev=check_wall_action(observed,self.SPEC)
        self.assertFalse(ok)
        self.assertTrue(ev["uncertain"])

    def test_negated_wall_contact_is_rejected_even_when_other_cues_match(self):
        captions=[
            "An adult leans forward, standing on both feet. Both hands do not touch the stone wall.",
            "An adult leans forward, standing on both feet. Both palms are not pressed against the stone wall.",
            "An adult leans forward, standing on both feet. Both hands never touch the stone wall.",
            "An adult leans forward, standing on both feet. Both hands are not on the stone wall.",
        ]
        for caption in captions:
            with self.subTest(caption=caption):
                ok,reasons,ev=check_wall_action(caption,self.SPEC)
                self.assertFalse(ok,(caption,reasons,ev))
                self.assertTrue(reasons)
                self.assertTrue(ev["wall_contact_negated"])

    def test_affirmative_wall_contact_remains_accepted(self):
        caption=("An adult leans forward, standing on both feet, "
                 "with both hands touching the stone wall.")
        ok,reasons,ev=check_wall_action(caption,self.SPEC)
        self.assertTrue(ok,(reasons,ev))
        self.assertFalse(ev["wall_contact_negated"])

    def test_unrelated_scenes_unaffected(self):
        spec={"composition":"neural_story","characters":[{"name":"Mira"}],
              "prompt":"Mira stands in a market square and waves."}
        self.assertFalse(wall_brace_required(spec))
        self.assertEqual(check_wall_action("",spec)[:2],(None,[]))

    def test_structured_spec_isolation(self):
        sample={"composition":"neural_story","characters":[{"name":"Mira"}],
            "prompt":("Semireal view from behind at medium distance: adult Mira "
                      "leans forward with both palms on the inner stone wall of "
                      "the Ash Gate arch, legs straight and back slightly arched.")}
        self.assertTrue(wall_brace_required(sample))

if __name__=="__main__":unittest.main()
