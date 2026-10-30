"""Model hashing and fail-closed observational behavior require no real weights."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
import identity_sface_shadow as test
class ModelProvenance(unittest.TestCase):
 def test_absent_model_never_returns_ok(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertFalse(test.model_integrity(td)['ok'])
   (Path(td)/'yunet.onnx').write_bytes(b'fake')
   self.assertFalse(test.model_integrity(td)['ok'])
   with self.assertRaises(ValueError):test.SFaceShadow(td)
 def test_models_pinned_to_independent_hashes(self):
  self.assertEqual(len(test.MODEL_SHA),2)
  self.assertEqual(len(set(test.MODEL_SHA.values())),2)
  self.assertTrue(all(len(x)==64 for x in test.MODEL_SHA.values()))
if __name__=='__main__':unittest.main()
