import hashlib,io,os,sys,tempfile,unittest,uuid
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from local_repair import (archive_rejected_candidate,load_candidate,cleanup,
                          apply_inpaint_graph,choose_repair_region,mask_source)
class Repair(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  os.environ["VN_REJECTED_REPAIR_DIR"]=self.tmp.name
  im=Image.new("RGBA",(768,512),(80,90,110,255))
  raw=io.BytesIO();im.save(raw,format="PNG");self.raw=raw.getvalue()
  self.job={"id":str(uuid.uuid4()),"kind":"scene","style":"realistic",
    "attempts":1,"spec":{"max_attempts":3,"resolution":[768,512],
    "visual_contract":{"version":1,"principals":[{"name":"A",
    "region":[.1,.2,.25,.6]}]}}}
 def tearDown(self):
  self.tmp.cleanup()
  os.environ.pop("VN_REJECTED_REPAIR_DIR",None)
 def test_accepted_path_and_graph_mask(self):
  self.assertTrue(archive_rejected_candidate(self.job,self.raw,[],"wardrobe"))
  retry={**self.job,"attempts":2,"error":"Wardrobe mismatch"}
  self.assertEqual(load_candidate(retry,"wardrobe")[1],[.1,.2,.25,.6])
  graph={"5":{"class_type":"KSampler","inputs":{"denoise":1,
          "latent_image":["2",0]}},"6":{"class_type":"VAEDecode"},
          "7":{"class_type":"SaveImage","inputs":{"images":["6",0]}}}
  uploads=[]
  self.assertTrue(apply_inpaint_graph(retry,graph,["1",2],
                   lambda raw,name:uploads.append((raw,name)) or name))
  self.assertEqual(graph["5"]["inputs"]["latent_image"],["91",0])
  self.assertEqual(graph["7"]["inputs"]["images"],["92",0])
  source=Image.open(io.BytesIO(uploads[0][0]))
  self.assertLess(source.getchannel("A").getpixel((150,200)),20)
  self.assertGreater(source.getchannel("A").getpixel((650,450)),245)
  cleanup(retry)
  self.assertIsNone(load_candidate(retry,"wardrobe"))
 def test_no_automatic_repair_when_actor_ambiguous(self):
  job={**self.job,"spec":{**self.job["spec"],
       "visual_contract":{"principals":[{"name":"A","region":[.1,.2,.3,.6]},
                         {"name":"B","region":[.5,.2,.3,.6]}]}}}
  self.assertFalse(archive_rejected_candidate(job,self.raw,[],"wardrobe"))
 def test_bad_region_or_modified_source_never_reused(self):
  self.assertTrue(archive_rejected_candidate(self.job,self.raw,[],"wardrobe"))
  retry={**self.job,"attempts":2}
  f=Path(self.tmp.name)/(self.job["id"]+".png")
  f.write_bytes(self.raw+b"x")
  self.assertIsNone(load_candidate(retry,"wardrobe"))
  self.assertFalse(choose_repair_region({**self.job,
      "spec":{"visual_contract":{"principals":[{"name":"A",
      "region":[0,0,1,1]}]}}},Image.new("RGB",(512,512)),"wardrobe"))
 def test_photo_repair_disabled_if_no_grounded_region(self):
  job={**self.job,"spec":{"max_attempts":3,"resolution":[768,512]}}
  self.assertFalse(archive_rejected_candidate(job,self.raw,[],"wardrobe"))
if __name__=="__main__":unittest.main()
