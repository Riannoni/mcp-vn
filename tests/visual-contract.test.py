import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from visual_contract import action_contrast_captions

class VisualContractTest(unittest.TestCase):
    def test_unconstrained_activity_and_pose_are_included(self):
        scene={"local_visual_state":{"activity":"they exchange a folded map",
          "characters":[{"name":"Guide","pose":"sitting on a bench","action":"hands over a folded map"},
                        {"name":"Traveler","pose":"kneeling beside the bench",
                         "action":"reaches toward the map"}]}}
        texts=action_contrast_captions(scene)
        self.assertIn("exchange a folded map",texts[0])
        self.assertIn("sitting",texts[0])
        self.assertIn("kneeling",texts[0])
        self.assertIn("motionless",texts[1])
    def test_no_activity_means_no_spurious_scoring(self):
        self.assertIsNone(action_contrast_captions({"local_visual_state":{
            "activity":"","characters":[{"name":"Traveler","pose":"standing"}]}}))
    def test_never_labels_any_activity_as_forbidden(self):
        plan={"local_visual_state":{"activity":"some newly invented action",
            "characters":[{"name":"Guide","pose":"arbitrary body movement",
                          "action":"a new gesture"}]}}
        self.assertIsNotNone(action_contrast_captions(plan))

if __name__=="__main__":
    unittest.main()
