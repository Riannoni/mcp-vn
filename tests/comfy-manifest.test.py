import os,tempfile,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from comfy_manifest import (key,persist,load,digest,
                            intent_path,load_intent,persist_intent)
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
 def test_graph_digest_is_stable(self):
  self.assertEqual(digest({"b":2,"a":1}),digest({"a":1,"b":2}))
 def test_pre_submit_intent_preserves_random_seed_after_lost_receipt(self):
  original={"5":{"class_type":"KSampler","inputs":{"seed":123456}}}
  intent=persist_intent(self.job,original)
  # Simulate backend accepted the POST but this process died before writing
  # its prompt receipt. The action still has durable graph/seed, no new seed.
  self.assertIsNone(load(self.job))
  self.assertEqual(load_intent(self.job)["graph"],original)
  self.assertEqual(intent["workflow_digest"],digest(original))
  self.assertEqual(intent_path(self.job).stat().st_mode&0o777,0o600)
  self.assertEqual(persist_intent(self.job,original),intent)
  with self.assertRaisesRegex(RuntimeError,"COMFY_INTENT_GRAPH_CONFLICT"):
   persist_intent(self.job,{"5":{"class_type":"KSampler","inputs":{"seed":654321}}})
 def test_bad_intent_cannot_silently_generate_second_job(self):
  graph={"5":{"class_type":"KSampler","inputs":{"seed":1}}}
  persist_intent(self.job,graph)
  changed={**self.job,"spec":{"spec_version":6}}
  with self.assertRaisesRegex(RuntimeError,"COMFY_INTENT_UNVERIFIED"):
   load_intent(changed)
  intent_path(self.job).write_text("{corrupt",encoding="utf-8")
  with self.assertRaisesRegex(RuntimeError,"COMFY_INTENT_UNVERIFIED"):
   load_intent(self.job)
 def test_identical_graph_for_distinct_action_ids_is_not_shared(self):
  graph={"5":{"class_type":"KSampler","inputs":{"seed":99}}}
  first=persist_intent(self.job,graph)
  different={**self.job,"id":"33333333-3333-4333-8333-333333333333"}
  second=persist_intent(different,graph)
  self.assertEqual(first["workflow_digest"],second["workflow_digest"])
  self.assertNotEqual(intent_path(self.job),intent_path(different))
  self.assertNotEqual(first["job_id"],second["job_id"])
if __name__=="__main__":unittest.main()
