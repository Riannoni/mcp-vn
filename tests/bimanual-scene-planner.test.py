import sys,unittest,io
from pathlib import Path
from PIL import Image,ImageOps
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from bimanual_scene_planner import plan_bimanual,make_edit_mask,BimanualPlanError

class BimanualScenePlanner(unittest.TestCase):
 def frame(self):
  v=[0.]*54
  for j,x,y in ((0,290,70),(1,290,120),(2,240,135),(3,220,200),
       (4,230,260),(5,340,135),(6,360,200),(7,350,260),
       (8,260,250),(9,260,325),(10,260,385),
       (11,320,250),(12,320,325),(13,320,385)):
   v[j*3:j*3+3]=[x,y,.99]
  actor={'pose_keypoints_2d':v}
  for hand,cx in (('hand_right_keypoints_2d',230),('hand_left_keypoints_2d',350)):
   actor[hand]=[q for i in range(21) for q in (cx+(i%5)-2,258+i//5,.98)]
  return {'canvas_width':600,'canvas_height':400,'people':[actor]}
 def plan(self,**changes):
  kw={'object_kind':'wooden_box','zone':'waist','width_ratio':.72,'aspect_ratio':.50}
  kw.update(changes)
  return plan_bimanual(self.frame(),0,**kw)
 def test_relative_waist_prop_both_wrist_targets(self):
  p=self.plan(); self.assertEqual(p['status'],'geometry_plan_not_visual_qa')
  b=p['prop_bbox'];self.assertGreater(b[0],240);self.assertLess(b[2],340)
  self.assertLess(b[3],250)
  self.assertAlmostEqual(p['prop_width_over_shoulders'],.72,places=2)
  v=p['source_pose']['people'][0]['pose_keypoints_2d']
  self.assertEqual(v[4*3],float(b[0]));self.assertEqual(v[7*3],float(b[2]))
  self.assertEqual(self.frame()['people'][0]['pose_keypoints_2d'][4*3],230)
 def test_chest_plan_higher_than_waist(self):
  c=self.plan(zone='chest',object_kind='paper_map',width_ratio=.82)
  w=self.plan()
  self.assertLess(c['prop_bbox'][1],w['prop_bbox'][1])
 def test_pose_no_magic_pixel_dependence(self):
  f=self.frame();g=self.frame()
  for actor in g['people']:
   v=actor['pose_keypoints_2d']
   for j in range(18):v[3*j]*=1.3;v[3*j+1]*=1.3
   for k in ('hand_left_keypoints_2d','hand_right_keypoints_2d'):
    vals=actor[k]
    for i in range(21):vals[3*i]*=1.3;vals[3*i+1]*=1.3
  g['canvas_width']=780;g['canvas_height']=520
  p=plan_bimanual(f,0,object_kind='wooden_box',zone='waist',width_ratio=.7,aspect_ratio=.4)
  q=plan_bimanual(g,0,object_kind='wooden_box',zone='waist',width_ratio=.7,aspect_ratio=.4)
  self.assertAlmostEqual(q['prop_bbox'][0]/p['prop_bbox'][0],1.3,places=2)
 def test_mask_contains_both_source_hands(self):
  f=self.frame();p=self.plan();mask=make_edit_mask(f,p)
  self.assertEqual(mask.size,(600,400))
  x=ImageOps.invert(mask.getchannel('A'))
  self.assertEqual(x.getpixel((230,260)),255)
  self.assertEqual(x.getpixel((350,260)),255)
  self.assertEqual(x.getpixel((290,65)),0)
  self.assertEqual(x.getpixel((260,382)),0)
 def test_invalid_camera_and_types_fail_closed(self):
  for kwargs in ({'view':'rear'},{'same_depth':False},{'width_ratio':2},
                 {'aspect_ratio':0},{'zone':'unknown'},{'object_kind':''}):
   with self.subTest(kwargs=kwargs),self.assertRaises(BimanualPlanError):self.plan(**kwargs)
 def test_ambiguous_principal_and_pose_fail_closed(self):
  f=self.frame()
  with self.assertRaises(BimanualPlanError):
   plan_bimanual(f,3,object_kind='box',zone='waist',width_ratio=.7,aspect_ratio=.4)
  f['people'][0]['pose_keypoints_2d'][2*3+2]=.01
  with self.assertRaises(BimanualPlanError):
   plan_bimanual(f,0,object_kind='box',zone='waist',width_ratio=.7,aspect_ratio=.4)
 def test_deterministic_mask_source_unchanged(self):
  f=self.frame();p=self.plan()
  a=make_edit_mask(f,p);b=make_edit_mask(f,p)
  self.assertEqual(a.tobytes(),b.tobytes())
  self.assertEqual(self.frame()['people'][0]['pose_keypoints_2d'],f['people'][0]['pose_keypoints_2d'])
if __name__=='__main__':unittest.main()
