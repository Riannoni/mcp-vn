import importlib.util, pathlib, tempfile,unittest,time
R=pathlib.Path(__file__).resolve().parents[1]/"scripts/prune-comfy-temp.py"
spec=importlib.util.spec_from_file_location("maintenance",R)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Maintenance(unittest.TestCase):
 def test_only_named_temp_and_older_than_retention(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   a=root/"mcp_vn_test.png";a.write_bytes(b"123")
   b=root/"canonical.png";b.write_bytes(b"private")
   old=time.time()-60*86400
   import os;os.utime(a,(old,old))
   found=list(m.candidates(root,30,time.time()))
   self.assertEqual([x[0].name for x in found],["mcp_vn_test.png"])
   self.assertTrue(b.exists())
if __name__=="__main__":unittest.main()
