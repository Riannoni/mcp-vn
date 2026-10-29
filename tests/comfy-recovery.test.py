"""Run the production worker GPU-output handoff against stubbed ComfyUI history."""
import io,os,sys,tempfile,uuid,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("VN_WORKER_TOKEN","test-not-real")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
import worker
class Recovery(unittest.TestCase):
 def test_same_accepted_prompt_not_submitted_twice(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)
   jobid=str(uuid.uuid4());pid=str(uuid.uuid4())
   job={"id":jobid,"kind":"scene","style":"realistic",
        "attempts":1,"prompt":"test","spec":{"resolution":[32,32]}}
   output=path/("mcp_vn_"+jobid+"_00001_.png")
   data=b"PNG test fixture bytes"
   output.write_bytes(data)
   history={pid:{"status":{"status_str":"success"},
          "outputs":{"7":{"images":[{"filename":output.name,
                                      "subfolder":""}]}}}}
   requests=[]
   def fake_request(base,endpoint,method="GET",body=None,*args,**kwargs):
    requests.append(endpoint)
    if endpoint=="/prompt":return {"prompt_id":pid}
    if endpoint=="/history/"+pid:return history
    raise AssertionError(endpoint)
   with patch.dict(os.environ,{"VN_COMFY_MANIFEST_DIR":str(path/"manifest")}),\
        patch.object(worker,"OUTPUT",path),patch.object(worker,"POLL",0),\
        patch.object(worker,"request",side_effect=fake_request):
    first=worker.run_comfy(job,{"5":{"class_type":"Sample"}})
    second=worker.run_comfy(job,{"5":{"class_type":"Sample"}})
   self.assertEqual(first,second)
   self.assertEqual(first[0],data)
   self.assertEqual(requests.count("/prompt"),1)
if __name__=="__main__":unittest.main()
