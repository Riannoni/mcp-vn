import copy,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from staged_klein_scene import attach_inpaint_to_klein_graph,StagedSceneError
class StagedKlein(unittest.TestCase):
 def base(self):
  return {'3':{'class_type':'VAELoader'},
   '10':{'class_type':'SamplerCustomAdvanced','inputs':{'latent_image':['5',0],
            'noise':['6',0]}},
   '11':{'class_type':'VAEDecode','inputs':{'samples':['10',0]}},
   '12':{'class_type':'SaveImage','inputs':{'images':['11',0],
                  'filename_prefix':'vn_private_test'}}}
 def test_composite_retains_original_graph(self):
  base=self.base();old=copy.deepcopy(base)
  g,meta=attach_inpaint_to_klein_graph(base,source_upload='vn-src.png',mask_upload='vn-mask.png')
  self.assertEqual(base,old)
  self.assertEqual(g['12']['inputs']['images'],[meta['nodes']['composite'],0])
  self.assertEqual(g['10']['inputs']['noise'],['6',0])
  self.assertEqual(g[meta['nodes']['masked_latent']]['class_type'],'SetLatentNoiseMask')
 def test_unsafe_graphs_and_uploads_fail(self):
  cases=[({'10':{'class_type':'KSampler'}},'vn-src.png','vn-mask.png'),
         (self.base(),'../secret.png','vn-mask.png'),
         (self.base(),'vn-src.png','some.txt')]
  for graph,src,mask in cases:
   with self.subTest(src=src):
    with self.assertRaises(StagedSceneError):attach_inpaint_to_klein_graph(graph,source_upload=src,mask_upload=mask)

# Additional test class discovered by unittest; no GPU or actual story content.
from io import BytesIO
from PIL import Image,ImageDraw
from staged_klein_scene import verify_mask,verify_output_preservation
class StrictImageGuards(unittest.TestCase):
 def png(self,im):
  b=BytesIO();im.save(b,format='PNG');return b.getvalue()
 def fixture(self):
  src=Image.new('RGB',(300,200),(120,90,75))
  mask=Image.new('RGBA',src.size,(0,0,0,255))
  a=mask.getchannel('A');ImageDraw.Draw(a).rectangle((110,80,210,180),fill=0)
  mask.putalpha(a)
  out=src.copy();ImageDraw.Draw(out).rectangle((130,100,170,150),fill=(5,240,20))
  return src,out,mask
 def test_protected_face_and_preservation(self):
  src,out,mask=self.fixture()
  self.assertEqual(verify_mask(self.png(mask),src.size,[(.1,.1,.3,.3)])['status'],
                   'preflight_only_qa_unverified')
  self.assertEqual(verify_output_preservation(self.png(src),self.png(out),self.png(mask))['status'],
                   'strict_pixels_preserved')
 def test_face_region_partially_editable_fails(self):
  src,out,mask=self.fixture()
  with self.assertRaisesRegex(StagedSceneError,'protected_pixels_would_change'):
   verify_mask(self.png(mask),src.size,[(.4,.5,.6,.7)])
 def test_mutated_locked_pixel_fails(self):
  src,out,mask=self.fixture()
  out.putpixel((22,22),(0,0,0))
  with self.assertRaisesRegex(StagedSceneError,'protected_pixels_changed_in_output'):
   verify_output_preservation(self.png(src),self.png(out),self.png(mask))
 def test_canvas_mismatch_fails(self):
  src,out,mask=self.fixture()
  with self.assertRaisesRegex(StagedSceneError,'dimensions'):
   verify_output_preservation(self.png(src),self.png(out.resize((200,200))),self.png(mask))

if __name__=='__main__':unittest.main()
