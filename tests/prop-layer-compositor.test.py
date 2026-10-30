import sys,unittest
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from prop_layer_compositor import PropLayerError,compose_bimanual_prop
class PropLayerTests(unittest.TestCase):
 def data(self):
  w,h=300,200;src=Image.new('RGB',(w,h),(99,109,124))
  ImageDraw.Draw(src).rectangle((98,35,202,146),fill=(35,48,85))
  gen=src.copy();d=ImageDraw.Draw(gen)
  d.rectangle((105,65,195,105),fill=(221,211,180))
  d.ellipse((98,72,122,95),fill=(204,152,128));d.ellipse((179,72,201,95),fill=(204,152,128))
  v=[0.]*54
  for i,x,y in ((2,120,45),(5,180,45)):v[3*i:3*i+3]=[x,y,.99]
  p={'pose_keypoints_2d':v}
  for key,cx in (('hand_right_keypoints_2d',111),('hand_left_keypoints_2d',190)):
   p[key]=[q for i in range(21) for q in (cx+(i%5)-2,80+i//5-2,.99)]
  return src,gen,{'canvas_width':w,'canvas_height':h,'people':[p]}
 def run_case(self,**kw):
  a,b,pose=self.data()
  defaults={'max_width_to_shoulders':1.,'design_width_to_shoulders':.8,
   'allowed_region':(70,35,230,155),'lower_body_lock_y':175,
   'protected_regions':((125,5,175,35),)}
  defaults.update(kw)
  return compose_bimanual_prop(a,b,pose,0,[[105,65,195,105]],(300,200),**defaults)
 def test_typed_ratio_and_immutable_pixels(self):
  result,report=self.run_case();self.assertEqual(report['planned_width_px'],48)
  self.assertLessEqual(report['planned_ratio'],.81)
  _,original,_=self.data();before=np.asarray(original);after=np.asarray(result)
  x0,y0,x1,y1=report['authorized_roi'];locked=np.ones((200,300),bool)
  locked[y0:y1,x0:x1]=False
  self.assertTrue(np.array_equal(before[locked],after[locked]))
  self.assertEqual(report['protected_pixels_identical'],int(locked.sum()))
 def test_unauthorized_roi_rejected(self):
  with self.assertRaisesRegex(PropLayerError,'outside_allowed'):
   self.run_case(allowed_region=(120,30,210,155))
 def test_face_or_leg_intersection_rejected(self):
  with self.assertRaisesRegex(PropLayerError,'protected_region'):
   self.run_case(protected_regions=((100,70,140,100),))
  with self.assertRaisesRegex(PropLayerError,'locked_lower'):
   self.run_case(lower_body_lock_y=100)
 def test_invalid_target_rejected(self):
  for ratio in (0,1.,1.2,None,float('nan'),True):
   with self.subTest(ratio=ratio),self.assertRaises(PropLayerError):
    self.run_case(design_width_to_shoulders=ratio)
 def test_wrong_canvas_and_multiple_objects_rejected(self):
  a,b,pose=self.data()
  kwargs={'max_width_to_shoulders':1.,'design_width_to_shoulders':.8,
   'allowed_region':(70,35,230,155),'lower_body_lock_y':175}
  with self.assertRaisesRegex(PropLayerError,'canvas'):
   compose_bimanual_prop(a,b.resize((299,200)),pose,0,[[105,65,195,105]],(300,200),**kwargs)
  for boxes in ([],[[105,65,195,105],[110,68,198,109]]):
   with self.assertRaisesRegex(PropLayerError,'ambiguous_object'):
    compose_bimanual_prop(a,b,pose,0,boxes,(300,200),**kwargs)
 def test_unobserved_hand_rejected(self):
  a,b,pose=self.data();p=pose['people'][0]
  for i in range(10):p['hand_right_keypoints_2d'][3*i+2]=0
  with self.assertRaisesRegex(PropLayerError,'hand_unobservable'):
   compose_bimanual_prop(a,b,pose,0,[[105,65,195,105]],(300,200),
    max_width_to_shoulders=1.,design_width_to_shoulders=.8,
    allowed_region=(70,35,230,155),lower_body_lock_y=175)
 def test_unsupported_view_and_depth_rejected(self):
  for override in ({'view':'rear'},{'same_depth':False}):
   with self.assertRaisesRegex(PropLayerError,'unsupported_view'):
    self.run_case(**override)
if __name__=='__main__':unittest.main()
