import os,tempfile,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from comfy_manifest import key,persist,load,digest
class Manifest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  os.environ["VN_COMFY_MANIFEST_DIR"]=self.tmp.name
  self.job={"id":"11111111-1111-4111-8111-111111111111","kind":"scene",
    "style":"realistic","attempts":1,"prompt":"one market","spec":{"spec_version":5}}
 def tearDown(self):
  self.tmp.cleanup()
  os.environ.pop("VN_COMFY_MANIFEST_DIR",None)
 def test_durable_resume_does_not_accept_altered_spec(self):
  item=persist(self.job,"22222222-2222-4222-8222-222222222222","sha")
  self.assertEqual(load(self.job)["prompt_id"],item["prompt_id"])
  self.assertEqual(key(self.job).stat().st_mode&0o777,0o600)
  changed={**self.job,"spec":{"spec_version":6}}
  self.assertIsNone(load(changed))
 def test_changed_workflow_cannot_resume_old_prompt(self):
  first=digest({"checkpoint":"A","steps":8})
  second=digest({"checkpoint":"B","steps":8})
  item=persist(self.job,"22222222-2222-4222-8222-222222222222",first)
  self.assertEqual(load(self.job,expected_workflow_digest=first)["prompt_id"],item["prompt_id"])
  with self.assertRaisesRegex(RuntimeError,"workflow digest mismatch"):
   load(self.job,expected_workflow_digest=second)
  with self.assertRaisesRegex(RuntimeError,"workflow digest mismatch"):
   load(self.job,expected_workflow_digest="")
 def test_missing_stored_workflow_digest_fails_closed(self):
  item=persist(self.job,"22222222-2222-4222-8222-222222222222",digest({"checkpoint":"A"}))
  path=key(self.job)
  import json
  payload=json.loads(path.read_text());payload.pop("workflow_digest")
  path.write_text(json.dumps(payload))
  with self.assertRaisesRegex(RuntimeError,"workflow digest mismatch"):
   load(self.job,expected_workflow_digest=item["workflow_digest"])
 def test_graph_digest_is_stable(self):
  self.assertEqual(digest({"b":2,"a":1}),digest({"a":1,"b":2}))
if __name__=="__main__":unittest.main()
