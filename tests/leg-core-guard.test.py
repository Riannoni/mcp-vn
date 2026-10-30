import unittest,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from leg_core_guard import LegCoreError,check_thigh_cores

class LegCore(unittest.TestCase):
    def pose(self):
        vector=[0]*54
        for i,x,y in ((8,130,120),(9,132,175),(11,170,120),(12,168,175)):
            vector[3*i:3*i+3]=[x,y,.99]
        return {"canvas_width":300,"canvas_height":200,"people":[{"pose_keypoints_2d":vector}]}
    def test_upper_body_edit_keeps_thigh_core(self):
        mask=Image.new("L",(300,200),0)
        ImageDraw.Draw(mask).rectangle((90,40,205,101),fill=255)
        report=check_thigh_cores(mask,self.pose(),0)
        self.assertEqual(report["status"],"source_pose_thigh_cores_locked")
        self.assertGreater(report["conservative_lock_pixels"],200)
    def test_wide_wardrobe_edit_fails(self):
        mask=Image.new("L",(300,200),0)
        ImageDraw.Draw(mask).rectangle((95,80,205,185),fill=255)
        with self.assertRaisesRegex(LegCoreError,"non_target_thigh"):
            check_thigh_cores(mask,self.pose(),0)
    def test_one_pixel_thigh_change_fails(self):
        mask=Image.new("L",(300,200),0);mask.putpixel((130,120),1)
        with self.assertRaisesRegex(LegCoreError,"non_target_thigh"):
            check_thigh_cores(mask,self.pose(),0)
    def test_low_confidence_fails(self):
        p=self.pose();p["people"][0]["pose_keypoints_2d"][9*3+2]=.1
        with self.assertRaisesRegex(LegCoreError,"unobservable"):
            check_thigh_cores(Image.new("L",(300,200)),p,0)
    def test_unattributed_or_invalid_canvas_fails(self):
        p=self.pose();m=Image.new("L",(300,200))
        for idx in (None,-1,9,True):
            with self.assertRaises(LegCoreError):check_thigh_cores(m,p,idx)
        with self.assertRaises(LegCoreError):
            check_thigh_cores(m.resize((320,200)),p,0)
    def test_missing_hips_fails(self):
        p=self.pose();p["people"][0]["pose_keypoints_2d"]=[]
        with self.assertRaises(LegCoreError):check_thigh_cores(Image.new("L",(300,200)),p,0)

if __name__=="__main__":unittest.main()
