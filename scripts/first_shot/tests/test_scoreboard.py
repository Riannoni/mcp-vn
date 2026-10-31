"""Fail-closed scoreboard negative/positive tests; CPU only, no GPU."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

base=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("first_shot_scoreboard",base/"scoreboard.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.png=self.root/"original.png"
        self.png.write_bytes(b"\x89PNG\r\n\x1a\n"+b"synthetic test only")
        self.sha=hashlib.sha256(self.png.read_bytes()).hexdigest()
        self.result={"case":"BG-01","first_attempt":1,"g1":"PASS","prompt_id":"a-frozen-trusted-prompt",
            "png_sha256":self.sha,"original_png_path":str(self.png),"total_submit_to_output_seconds":13.4}
        self.review={"case":"BG-01","prompt_id":self.result["prompt_id"],"png_sha256":self.sha,
                     "original_pixels_reviewed":True,"mandatory":["environment"],"checks":{"environment":"verified"}}
        self.write()
    def write(self):
        (self.root/"BG-01-result.json").write_text(json.dumps(self.result))
        (self.root/"BG-01-pixel-review.json").write_text(json.dumps(self.review))
    def check(self):
        return m.evaluate(self.root)["cases"][0]
    def test_exact_firstshot_review_can_pass(self):
        self.assertEqual(self.check()["g2"],"PASS")
    def test_unobservable_never_passes(self):
        self.review["checks"]["environment"]="unobservable";self.write()
        self.assertEqual(self.check()["g2"],"FAIL")
    def test_invalid_source_sha_not_accepted(self):
        self.png.write_bytes(b"changed")
        self.assertIn("original_pixel_hash_mismatch",self.check()["failures"])
    def test_wrong_prompt_link_denied(self):
        self.review["prompt_id"]="another prompt";self.write()
        self.assertIn("review_not_linked_to_exact_prompt_png",self.check()["failures"])
    def test_no_review_is_not_auto_pass(self):
        (self.root/"BG-01-pixel-review.json").unlink()
        self.assertEqual(self.check()["g2"],"NOT_REVIEWED")
    def test_repair_cannot_claim_first_attempt(self):
        self.result["first_attempt"]=2;self.write()
        self.assertIn("invalid_first_attempt_or_G1",self.check()["failures"])
    def test_not_applicable_mandatory_field_rejected(self):
        self.review["checks"]["environment"]="not_applicable";self.write()
        self.assertEqual(self.check()["g2"],"FAIL")

if __name__=="__main__": unittest.main()
