import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from engine_policy import read_engine_contract,assert_engine_snapshot
from actor_layout import MAX_CG_FACE_ANCHORS
class EnginePolicyTests(unittest.TestCase):
 def test_contract_is_global(self):
  doc=read_engine_contract()
  self.assertEqual(doc['engine_id'],'mcp-vn')
  self.assertEqual(doc['contract_version'],1)
  self.assertEqual(MAX_CG_FACE_ANCHORS,doc['render']['max_anchored_principals_per_pass'])
  self.assertFalse(doc['import']['network_fetch_enabled'])
 def test_version_drift_is_rejected(self):
  doc=read_engine_contract()
  r=doc['render']
  spec={'engine_id':doc['engine_id'],'contract_version':doc['contract_version'],
    'render_profile':r['profile'],'pose_catalog':r['pose_catalog'],
    'qa_policy':r['qa_policy'],
    'max_anchored_principals_per_pass':r['max_anchored_principals_per_pass']}
  self.assertTrue(assert_engine_snapshot(spec))
  self.assertTrue(assert_engine_snapshot(None))
  with self.assertRaises(ValueError):
   assert_engine_snapshot({**spec,'qa_policy':'loose'})
if __name__=='__main__':unittest.main()
