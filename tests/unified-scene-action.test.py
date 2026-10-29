"""Narrator paraphrase regression: one contract across selector, prompt and QA."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from scene_action_contract import (
    resolve_scene_action,wall_brace_required,action_prompt_contract,check_wall_action)
from pose_reference_selector import scene_action_key
from scene_constraints import scene_constraints
from scene_caption_contract import scene_action_conflicts

def spec(prompt,pose="leaning forward against wall"):
    return {"composition":"neural_story",
            "environment":{"id":"outdoor_market_square"},
            "characters":[{"name":"Adult","outfit":"blue travel jacket","pose":pose}],
            "prompt":prompt}

class UnifiedActionTests(unittest.TestCase):
    def test_three_real_narrator_phrasings(self):
        cases=[
         ("One adult woman leans forward against the stone wall beside the arch, "
          "palms planted, back arched slightly, legs apart, head lowered. "
          "Rear three-quarter medium shot shows her back.","rear"),
         ("One adult woman stands close to a rough stone wall beside the gate "
          "and leans forward with both palms planted on it, back slightly arched "
          "and bare feet on paving. Medium-distance side view.","side"),
         ("Semireal view from behind: adult woman leans forward with both palms "
          "on the inner stone wall, legs straight and back slightly arched.","rear"),
        ]
        for prompt,camera in cases:
            with self.subTest(camera=camera,prompt=prompt[:45]):
                c=resolve_scene_action(spec(prompt),prompt)
                self.assertTrue(c["required"],c)
                self.assertEqual(c["action"],"palms_on_wall_hip_hinge")
                self.assertEqual(c["camera"],camera)
                self.assertEqual(scene_action_key(prompt,
                    spec(prompt)["characters"]),("palms_on_wall_hip_hinge",camera))
                pos,neg=action_prompt_contract(spec(prompt),prompt)
                self.assertIn("Both palms press flat",pos)
                self.assertIn("kneeling",neg)
                built,_=scene_constraints(spec(prompt),prompt)
                self.assertIn("PHYSICAL ACTION CONTRACT",built)
                reasons=scene_action_conflicts(spec(prompt)["characters"],
                    "A woman is kneeling on the ground next to a wall.",prompt)
                self.assertTrue(reasons)

    def test_one_hand_never_forces_two_hand_controlnet(self):
        prompt=("One adult leans toward a stone wall, left hand planted "
                "on its masonry, right hand holding a bag; rear view.")
        c=resolve_scene_action(spec(prompt),prompt)
        self.assertFalse(c["required"],c)
        self.assertEqual(c["reason"],"single_hand_action_has_no_approved_two_hand_guide")
        self.assertEqual(action_prompt_contract(spec(prompt),prompt),("",""))

    def test_missing_camera_is_fail_closed(self):
        prompt="One person leans forward against the stone wall, both palms planted."
        c=resolve_scene_action(spec(prompt),prompt)
        self.assertTrue(c["required"])
        self.assertIsNone(c["camera"])

    def test_nearby_wall_not_a_wall_brace(self):
        prompts=[
            "A woman stands near a rear wall with arms crossed.",
            "The woman leans near the rear wall, palms planted on paving stones.",
            "A woman leaning forward in a courtyard, hands on the ground. Stone wall behind.",
            "Two friends walk around the market, walls and palms in background.",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertFalse(resolve_scene_action(spec(prompt,pose="walking"),prompt)["required"])
                self.assertEqual(action_prompt_contract(spec(prompt,pose="walking"),prompt),("",""))

    def test_rear_wall_does_not_mean_rear_camera(self):
        prompt=("The woman leans against the rear wall with both palms "
                "pressed on stone. She is leaning forward.")
        c=resolve_scene_action(spec(prompt),prompt)
        self.assertTrue(c["required"])
        self.assertIsNone(c["camera"])

    def test_explicit_unrelated_scene_unchanged(self):
        prompt="One adventurer walks toward the fountain in the square."
        s=spec(prompt,pose="walking")
        self.assertFalse(wall_brace_required(s))
        self.assertEqual(check_wall_action("a woman walks",s)[:2],(None,[]))

if __name__=="__main__":
    unittest.main()
