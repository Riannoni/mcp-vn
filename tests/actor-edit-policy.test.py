import sys,unittest
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from staged_klein_scene import verify_mask, verify_output_preservation, StagedSceneError

class StationaryMapMask(unittest.TestCase):
    def png(self, img):
        b=BytesIO();img.save(b,format="PNG");return b.getvalue()
    def source_pose(self):
        body=[0.] * 54
        def joint(i,x,y):
            body[i*3:i*3+3] = [x,y,.96]
        for i,x,y in [(8,130,124),(9,130,145),(10,131,187),(11,173,124),(12,173,145),(13,174,186)]:
            joint(i,x,y)
        person={"pose_keypoints_2d":body}
        for hand, cx in (("hand_left_keypoints_2d",125),("hand_right_keypoints_2d",182)):
            coords=[]
            for i in range(21):
                coords += [cx+(i%5)*.5, 88+(i//5)*.5, .99]
            person[hand]=coords
        return {"canvas_width":300,"canvas_height":200,"people":[person]}
    def mask(self, lower=False):
        im=Image.new("RGBA",(300,200),(0,0,0,255))
        a=im.getchannel("A")
        ImageDraw.Draw(a).rectangle((100,72,214,192 if lower else 113),fill=0)
        im.putalpha(a)
        return im
    def verify(self, mask, pose=None, **kwargs):
        return verify_mask(self.png(mask),(300,200),[(.44,.10,.56,.27)],
            source_pose=self.source_pose() if pose is None else pose,principal_index=0,
            actor_change_policy={"action":"stationary_upper_body_prop","keypoint_format":"openpose18"},**kwargs)
    def test_valid_typed_bimanual_edit_preserves_both_feet(self):
        report=self.verify(self.mask())
        self.assertEqual(report["anatomy_lock"]["status"],"lower_body_locked")
        self.assertEqual(report["source_hand_coverage"]["verdict"],"covered_for_replacement")
        self.assertGreater(report["anatomy_lock"]["locked_lower_pixels"],0)
    def test_prior_full_body_silhouette_mask_fails_before_gpu(self):
        # The original generic face-only guard would permit this mask.
        m=self.mask(lower=True)
        self.assertEqual(verify_mask(self.png(m),(300,200),[(.44,.10,.56,.27)],
            source_pose=self.source_pose(),principal_index=0)["status"],"preflight_only_qa_unverified")
        with self.assertRaisesRegex(StagedSceneError,"non_target_lower_body_editable"):
            self.verify(m)
    def test_strict_thigh_core_accepts_original_small_hand_region(self):
        from io import BytesIO
        r=verify_mask(self.png(self.mask()),(300,200),[(.44,.10,.56,.27)],
            source_pose=self.source_pose(),principal_index=0,
            actor_change_policy={"action":"stationary_upper_body_prop_strict"})
        self.assertEqual(r["anatomy_lock"]["thigh_cores"]["status"],"source_pose_thigh_cores_locked")
    def test_strict_thigh_core_rejects_edit_of_unchanged_pants(self):
        m=self.mask();alpha=m.getchannel("A")
        ImageDraw.Draw(alpha).rectangle((125,110,135,128),fill=0)
        m.putalpha(alpha)
        # This edit is ABOVE the observed lower-shin protection boundary.
        normal=verify_mask(self.png(m),(300,200),[(.44,.10,.56,.27)],
            source_pose=self.source_pose(),principal_index=0,
            actor_change_policy={"action":"stationary_upper_body_prop"})
        self.assertEqual(normal["anatomy_lock"]["status"],"lower_body_locked")
        with self.assertRaisesRegex(StagedSceneError,"non_target_thigh_garment_editable"):
            verify_mask(self.png(m),(300,200),[(.44,.10,.56,.27)],
              source_pose=self.source_pose(),principal_index=0,
              actor_change_policy={"action":"stationary_upper_body_prop_strict"})
    def test_unobservable_knee_fails_closed(self):
        p=self.source_pose();p["people"][0]["pose_keypoints_2d"][9*3+2]=.1
        with self.assertRaisesRegex(StagedSceneError,"lower_leg_landmarks_unobservable"):
            self.verify(self.mask(),pose=p)
    def test_missing_source_attribution_fails(self):
        with self.assertRaisesRegex(StagedSceneError,"actor_policy_requires_attributed_source_pose"):
            verify_mask(self.png(self.mask()),(300,200),[(.44,.1,.56,.27)],
                actor_change_policy={"action":"stationary_upper_body_prop"})
    def test_wrong_layout_fails_closed(self):
        p=self.source_pose();p["people"][0]["pose_keypoints_2d"]=[]
        with self.assertRaisesRegex(StagedSceneError,"lower_leg_landmarks_unobservable"):
            self.verify(self.mask(),pose=p)
    def test_unapproved_action_and_wrong_layout(self):
        with self.assertRaisesRegex(StagedSceneError,"unsupported_actor_change_policy"):
            verify_mask(self.png(self.mask()),(300,200),[(.44,.1,.56,.27)],
                source_pose=self.source_pose(),principal_index=0,actor_change_policy={"action":"walking"})
        with self.assertRaisesRegex(StagedSceneError,"actor_edit_policy_rejected"):
            verify_mask(self.png(self.mask()),(300,200),[(.44,.1,.56,.27)],
                source_pose=self.source_pose(),principal_index=0,
                actor_change_policy={"action":"stationary_upper_body_prop","keypoint_format":"unknown"})
    def test_output_locked_foot_pixel_mutation_fails(self):
        src=Image.new("RGB",(300,200),"white")
        out=src.copy();out.putpixel((150,180),(0,0,0))
        with self.assertRaisesRegex(StagedSceneError,"protected_pixels_changed_in_output"):
            verify_output_preservation(self.png(src),self.png(out),self.png(self.mask()))
    def test_canvas_and_alpha_fail(self):
        with self.assertRaisesRegex(StagedSceneError,"mask_canvas_mismatch"):
            self.verify(self.mask().resize((320,200)))
        with self.assertRaisesRegex(StagedSceneError,"mask_must_have_alpha"):
            self.verify(self.mask().convert("RGB"))

if __name__=="__main__":unittest.main()
