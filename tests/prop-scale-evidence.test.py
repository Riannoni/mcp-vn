import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prop_scale_evidence import assess

class RelativeScale(unittest.TestCase):
    def frame(self):
        vec=[0]*54
        for joint,x,y in [(2,600,200),(5,400,202)]:vec[joint*3:joint*3+3]=[x,y,.99]
        return {"canvas_width":1000,"canvas_height":600,"people":[{"pose_keypoints_2d":vec}]}
    def check(self,boxes,frame=None,**kwargs):
        opt={"max_object_to_shoulder_ratio":1.,"view":"front","same_depth":True};opt.update(kwargs)
        return assess(self.frame() if frame is None else frame,0,boxes,(1000,600),**opt)
    def test_large_prop_relative_to_shoulders_is_violation(self):
        r=self.check([[350,170,650,350]]);self.assertEqual(r["verdict"],"violated");self.assertEqual(r["projected_ratio"],1.5)
    def test_smaller_prop_is_only_plausible(self):
        r=self.check([[445,170,555,350]]);self.assertEqual(r["verdict"],"plausible");self.assertEqual(r["projected_ratio"],.55)
    def test_different_detector_resolution(self):
        r=assess(self.frame(),0,[[222.5,170,277.5,350]],(500,600),max_object_to_shoulder_ratio=1,view="front",same_depth=True)
        self.assertEqual(r["projected_ratio"],.55)
    def test_missing_object_or_multiple_boxes_unobservable(self):
        for boxes in ([],[[1,2,30,40],[50,60,90,100]]):
            self.assertEqual(self.check(boxes)["verdict"],"unobservable")
    def test_no_source_attribution_or_unclear_shoulders_unobservable(self):
        bad=self.frame();bad["people"][0]["pose_keypoints_2d"][2*3+2]=.2
        self.assertEqual(self.check([[400,100,580,300]],frame=bad)["verdict"],"unobservable")
        self.assertEqual(assess(self.frame(),9,[[400,100,580,300]],(1000,600),max_object_to_shoulder_ratio=1,view="front",same_depth=True)["verdict"],"unobservable")
    def test_unsupported_view_depth_and_untyped_target_rejected(self):
        for kw in ({"view":"rear"},{"same_depth":False},{"max_object_to_shoulder_ratio":None}):
            self.assertEqual(self.check([[400,100,580,300]],**kw)["verdict"],"unobservable")
    def test_invalid_bbox(self):
        for box in ([600,100,400,300],[-1,100,400,300],[0,0,1001,500]):
            self.assertEqual(self.check([box])["verdict"],"unobservable")
    def test_projected_boundary_is_not_verified(self):
        self.assertEqual(self.check([[400,100,600,300]])["verdict"],"plausible")
if __name__=="__main__":unittest.main()
