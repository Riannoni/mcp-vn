"""Source-only regression for negated ground references in action captions."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from scene_caption_contract import scene_action_conflicts

ACTORS = [{"name": "Mira", "pose": "leaning forward"}]
PROMPT = "Mira leans forward with both hands pressed against the stone wall."
GROUND_VETO = "CG hands are on the ground instead of on the required wall"


class GroundPolarityTests(unittest.TestCase):
    def check(self, caption):
        return scene_action_conflicts(ACTORS, caption, PROMPT)

    def test_negated_pavement_does_not_veto_wall_contact(self):
        self.assertEqual(self.check(
            "Both hands touch wall, not pavement. She leans forward."), [])

    def test_negated_ground_does_not_veto_wall_contact(self):
        self.assertEqual(self.check(
            "Both hands on wall, not ground. She leans forward."), [])

    def test_affirmative_ground_contact_still_vetoes(self):
        self.assertIn(GROUND_VETO, self.check(
            "Both hands touch pavement, not wall. She kneels."))

    def test_later_affirmative_ground_contact_still_vetoes(self):
        self.assertIn(GROUND_VETO, self.check(
            "Both hands touch wall, not pavement. Later her hands rest on ground."))

    def test_unrelated_scene_unchanged(self):
        self.assertEqual(scene_action_conflicts(
            ACTORS, "A woman walks across the market.",
            "Mira walks across the market."), [])


if __name__ == "__main__":
    unittest.main()
