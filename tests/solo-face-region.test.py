import ast,unittest
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1]/"worker"/"worker.py"
class SoloRegion(unittest.TestCase):
 def test_single_actor_has_independent_face_mask_not_full_image(self):
  code=SOURCE.read_text()
  src=code.split("def regional_face_attention_mask(",1)[1].split("\ndef ",1)[0]
  self.assertIn("if count==1 and region is None:",src)
  self.assertIn("region=[.18,.04,.64,.92]",src)
  neural=code.split('elif kind=="scene" and spec.get("composition")=="neural_story"',1)[1].split('elif kind=="scene" and background',1)[0]
  self.assertIn('adapter["attn_mask"]=[mask_node,1]',neural)
  self.assertNotIn("if len(people)>1:",neural)
if __name__=="__main__":unittest.main()
