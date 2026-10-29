import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from pose_reference_selector import scene_action_key,choose_approved_reference
from PIL import Image

class RefTests(unittest.TestCase):
 def test_exact_semantics_and_no_guessing(self):
  self.assertEqual(scene_action_key(
   "One adult leaning forward, both palms on the stone wall, side view"),
   ("palms_on_wall","side"))
  self.assertEqual(scene_action_key(
   "One adult leaning forward, both palms on the stone wall, rear view"),
   ("palms_on_wall","rear"))
  self.assertEqual(scene_action_key(
   "Someone standing near the rear door"),(None,None))

 def test_unapproved_cannot_be_selected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   (root/"manifest.json").write_text(json.dumps([{"id":"x",
    "action":"palms_on_wall","camera":"side","status":"draft","approved":False}]))
   pose,why=choose_approved_reference(
       "Leaning forward with both palms against the stone wall, side view",root)
   self.assertIsNone(pose)
   self.assertEqual(why,"no_approved_exact_match")

 def test_approval_requires_integrity_and_documented_review(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   (root/"refs").mkdir()
   (root/"guides").mkdir()
   source=root/"refs"/"sample.jpg"
   source.write_bytes(b"private reference metadata")
   guide=root/"guides"/"sample.png"
   Image.new("RGB",(1216,704),(0,0,0)).save(guide)
   sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
   item={"id":"sample","action":"palms_on_wall","camera":"side",
    "status":"approved","approved":True,"extraction_status":"generated",
    "body_joints_confident":18,
    "reference":"refs/sample.jpg","reference_sha256":sha(source),
    "guide":"guides/sample.png","guide_sha256":sha(guide),
    "review":{"qa_passed":True,"ab_better":True,
              "reviewed_at":"2026-10-29","reviewer":"reviewer"}}
   manifest=root/"manifest.json"
   manifest.write_text(json.dumps([item]))
   prompt="An adult leaning forward with both palms on the stone wall, side view"
   entry,reason=choose_approved_reference(prompt,root)
   self.assertEqual(reason,"approved")
   self.assertEqual(entry["name"],"sample")
   guide.write_bytes(guide.read_bytes()+b"changed")
   entry,reason=choose_approved_reference(prompt,root)
   self.assertIsNone(entry)
   self.assertEqual(reason,"guide_hash_mismatch")

if __name__=="__main__":
 unittest.main()
