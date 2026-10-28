#!/usr/bin/env python3
"""No-GPU regression tests for transient ROCm/CPU KoboldCpp routing."""
from pathlib import Path
import importlib.util, os, unittest
from unittest.mock import patch
p=Path.home()/".local/share/mcp-vn-kobold/gateway.py"
spec=importlib.util.spec_from_file_location("vn_gateway",p)
g=importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
class BackendTests(unittest.TestCase):
 def setUp(self):g.ROCM_DISABLED.clear()
 def tearDown(self):g.ROCM_DISABLED.clear()
 def test_gpu_opt_in(self):
  with patch.dict(os.environ,{"VN_KOBOLD_BACKEND":"rocm","VN_KOBOLD_CPU_ONLY":"0"}):
   self.assertEqual(g.backend_for(g.MODEL_ID),"rocm")
   self.assertEqual(g.backend_for(g.CYDONIA_ID),"rocm")
   g.ROCM_DISABLED.add(g.CYDONIA_ID)
   self.assertEqual(g.backend_for(g.CYDONIA_ID),"cpu")
   self.assertEqual(g.backend_for(g.MODEL_ID),"rocm")
 def test_cpu_remains_safe_default_and_override(self):
  with patch.dict(os.environ,{"VN_KOBOLD_BACKEND":"cpu","VN_KOBOLD_CPU_ONLY":"0"}):
   self.assertEqual(g.backend_for(g.MODEL_ID),"cpu")
  with patch.dict(os.environ,{"VN_KOBOLD_BACKEND":"rocm","VN_KOBOLD_CPU_ONLY":"1"}):
   self.assertEqual(g.backend_for(g.MODEL_ID),"cpu")
 def test_failure_disables_rocm_and_retries_cpu_once(self):
  sample={"messages":[{"role":"user","content":"Hi"}],"model":g.MODEL_ID,"options":{"num_predict":64}}
  invoked=[]
  def runner(*args):
   mode=args[-1];invoked.append(mode)
   if mode=="rocm":raise RuntimeError("temporary ROCm backend failure")
   return {"backend":"koboldcpp-cpu","message":{"role":"assistant","content":"CPU response"}}
  with patch.dict(os.environ,{"VN_KOBOLD_BACKEND":"rocm","VN_KOBOLD_CPU_ONLY":"0"}):
   with patch.object(g,"http_json",return_value={"queue_running":[],"queue_pending":[]}):
    with patch.object(g,"run_single_inference",side_effect=runner):
     result=g.generate(sample)
     self.assertEqual(result["backend"],"koboldcpp-cpu")
     self.assertEqual(invoked,["rocm","cpu"])
     self.assertIn(g.MODEL_ID,g.ROCM_DISABLED)
     result=g.generate(sample)
     self.assertEqual(invoked,["rocm","cpu","cpu"])
if __name__=="__main__":unittest.main(verbosity=2)
