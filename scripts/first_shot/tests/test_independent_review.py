"""Offline negative tests for independent exact-original review receipts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

p=Path(__file__).resolve().parents[1]/"independent_review.py"
spec=importlib.util.spec_from_file_location("independent_review",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class GoldenReviewTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        for d in ("runs/CG03_LEAN_V2","review_pending","reviewed"):
            (self.root/d).mkdir(parents=True,exist_ok=True)
        self.png=self.root/"image.png"
        self.png.write_bytes(b"\x89PNG\r\n\x1a\n"+b"fake data only for SHA test")
        self.sha=hashlib.sha256(self.png.read_bytes()).hexdigest()
        self.result=dict(status="GPU_FINISHED_REVIEW_REQUIRED",
                         prompt_id="uuid-placeholder",png_sha256=self.sha,
                         original_png_path=str(self.png))
        self.review=dict(experiment_id="CG03_LEAN_V2",reviewer_task="G-10",
                         prompt_id=self.result["prompt_id"],png_sha256=self.sha,
                         original_pixels_reviewed=True,mandatory={"pose":"violated","contact":"verified"},
                         observations="The torso has insufficient forward angle; hands appear near stone.")
        self.rf=self.root/"review.json"
        self.save()
        (self.root/"review_pending/CG03_LEAN_V2.json").write_text("{}")
    def save(self):
        self.rf.write_text(json.dumps(self.review))
        (self.root/"runs/CG03_LEAN_V2/result.json").write_text(json.dumps(self.result))
    def test_failing_candidate_releases_one_review_fence(self):
        self.assertEqual(m.audit(self.root,self.rf)["g2"],"FAIL")
        self.assertTrue((self.root/"reviewed/CG03_LEAN_V2.json").exists())
        with self.assertRaises(ValueError):m.audit(self.root,self.rf)
    def test_wrong_hash_never_releases(self):
        self.review["png_sha256"]="0"*64;self.save()
        with self.assertRaises(ValueError):m.audit(self.root,self.rf)
    def test_no_real_pixels_never_passes(self):
        self.review["original_pixels_reviewed"]=False;self.save()
        with self.assertRaises(ValueError):m.audit(self.root,self.rf)
    def test_other_lane_cannot_self_review(self):
        self.review["reviewer_task"]="R-12";self.save()
        with self.assertRaises(ValueError):m.audit(self.root,self.rf)
    def test_missing_original_cannot_be_reviewed(self):
        self.png.unlink()
        with self.assertRaises(ValueError):m.audit(self.root,self.rf)
    def test_no_canonical_reference_cannot_mark_g2_pass(self):
        self.review["mandatory"]={"pose":"verified","contact":"verified"};self.save()
        self.assertEqual(m.audit(self.root,self.rf)["g2"],"UNVERIFIED")
if __name__=="__main__": unittest.main()
