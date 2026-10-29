import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from scene_caption_contract import scene_action_conflicts
class PoseTests(unittest.TestCase):
 def test_wall_action(self):
  spec=[{'name':'Mira','pose':'leaning'}]
  scene='One character leaning forward, both palms pressed against a vertical stone wall, rear view.'
  self.assertTrue(scene_action_conflicts(spec,'A person is reclining on the paving.',scene))
  self.assertFalse(scene_action_conflicts(spec,'A person stands and leans toward the wall.',scene))
if __name__=='__main__':unittest.main()
