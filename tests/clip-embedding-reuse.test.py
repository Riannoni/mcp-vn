"""Regression: expensive visual CLIP encoding is shared between banks.

No torch downloads are needed for this static wiring contract; the production
model itself is checked in an isolated live probe before deployment.
"""
import pathlib
import unittest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"worker"/"vision_daemon.py"
class EmbeddingReuse(unittest.TestCase):
    def test_one_embedding_per_scene(self):
        src=SOURCE.read_text()
        block=src.split("def analyze(",1)[1].split("class Handler(",1)[0]
        self.assertIn('clip_embedding=image_embedding(image) if kind in ("background","scene") else None',block)
        self.assertIn("score_environment(image,clip_embedding)",block)
        self.assertIn("score_principal_people(image,clip_embedding)",block)
        self.assertIn("score_action_contrast(image,spec,clip_embedding)",block)
        for name in ("score_environment","score_principal_people","score_action_contrast"):
            function=src.split("def "+name+"(",1)[1].split("\ndef ",1)[0]
            self.assertIn("embedding if embedding is not None else image_embedding(image)",function)
            self.assertNotIn("clip.get_image_features(",function)

if __name__=="__main__":
    unittest.main()
