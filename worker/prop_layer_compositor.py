"""Shadow-only bimanual prop geometry composition.

A deterministic extra stage for *already* generated, independently grounded
front-view actor+prop frames. This is not a scene verifier or production
publisher and NEVER silently substitutes a G2 pass.
"""
from __future__ import annotations
from math import isfinite
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


class PropLayerError(ValueError):
    pass


def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and isfinite(x)


def compose_bimanual_prop(
    baseline, generated, pose_frame, principal_index, object_boxes, detector_size,
    *, max_width_to_shoulders, design_width_to_shoulders, allowed_region,
    lower_body_lock_y, protected_regions=(), view="front", same_depth=True,
):
    """Return (PIL RGB image, non-authoritative evidence).

    Baseline must be a separately accepted *prop-free* actor/environment plate;
    generated must depict the same actor/outfit/background with an object and
    independently detected bilateral hands. The caller must verify those
    prerequisites. All candidate pixels outside one explicit allowed ROI are
    exactly preserved from generated; no accepted canonical asset is mutated.
    """
    if not isinstance(baseline, Image.Image) or not isinstance(generated, Image.Image):
        raise PropLayerError("missing_image")
    if baseline.size != generated.size or baseline.size[0]<128 or baseline.size[1]<128:
        raise PropLayerError("canvas_mismatch")
    w,h=generated.size
    if view!="front" or same_depth is not True:
        raise PropLayerError("unsupported_view_or_depth")
    if not (_number(max_width_to_shoulders) and _number(design_width_to_shoulders)
            and 0<design_width_to_shoulders<max_width_to_shoulders<=1.2):
        raise PropLayerError("invalid_typed_prop_size")
    if (not isinstance(pose_frame,dict) or isinstance(principal_index,bool)
            or not isinstance(principal_index,int)):
        raise PropLayerError("missing_attributed_pose")
    if not isinstance(object_boxes,(list,tuple)) or len(object_boxes)!=1:
        raise PropLayerError("ambiguous_object_box")
    if not isinstance(detector_size,(list,tuple)) or len(detector_size)!=2 or not all(
            _number(v) and v>0 for v in detector_size):
        raise PropLayerError("invalid_detector_canvas")
    dw,dh=detector_size
    try:
        if pose_frame["canvas_width"]!=w or pose_frame["canvas_height"]!=h:
            raise PropLayerError("pose_canvas_mismatch")
        people=pose_frame["people"]
        if not 0<=principal_index<len(people):
            raise PropLayerError("ambiguous_principal")
        person=people[principal_index]
        body=person["pose_keypoints_2d"]
        if len(body)!=54:raise PropLayerError("wrong_pose_layout")
        def joint(idx):
            p=list(map(float,body[3*idx:3*idx+3]))
            if (len(p)!=3 or not all(_number(v) for v in p)
                    or p[2]<.75 or not (0<=p[0]<w and 0<=p[1]<h)):
                raise PropLayerError("source_pose_unobservable")
            return p
        shoulders=(joint(2),joint(5))
        span=abs(shoulders[1][0]-shoulders[0][0])
        if not .035*w<span<.3*w:
            raise PropLayerError("shoulders_unobservable")
        hands=[]
        for key in ("hand_right_keypoints_2d","hand_left_keypoints_2d"):
            raw=person[key]
            if len(raw)!=63:raise PropLayerError("hand_keypoints_missing")
            points=[list(map(float,raw[3*i:3*i+3])) for i in range(21)]
            if any(len(v)!=3 or not all(_number(q) for q in v) for v in points):
                raise PropLayerError("hand_keypoints_invalid")
            visible=[p for p in points if p[2]>=.65 and 0<=p[0]<w and 0<=p[1]<h]
            if len(visible)<19:raise PropLayerError("hand_unobservable")
            hands.append(visible)
        if not isinstance(object_boxes[0],(list,tuple)) or len(object_boxes[0])!=4:
            raise PropLayerError("invalid_object_box")
        a,b,c,d=map(float,object_boxes[0])
        if not all(_number(v) for v in (a,b,c,d)) or not (0<=a<c<=dw and 0<=b<d<=dh):
            raise PropLayerError("invalid_object_box")
        x0,x1=a*w/dw,c*w/dw
        y0,y1=b*h/dh,d*h/dh
        object_width=x1-x0
        if object_width<span*1.1:
            raise PropLayerError("not_a_measurable_oversized_prop")
        cx,cy=(x0+x1)/2,(y0+y1)/2
        planned_w=int(round(span*design_width_to_shoulders))
        planned_h=max(8,int(round((y1-y0)*planned_w/object_width)))
        px=int(round(cx-planned_w/2));py=int(round(cy-planned_h/2))
        roi=(max(0,int(x0)-25),max(0,int(y0)-17),
             min(w,int(x1)+26),min(h,int(y1)+20))
        if (not isinstance(allowed_region,(tuple,list)) or len(allowed_region)!=4
                or not all(isinstance(v,int) for v in allowed_region)):
            raise PropLayerError("allowed_region_missing")
        ax0,ay0,ax1,ay1=allowed_region
        if not (0<=ax0<=roi[0]<roi[2]<=ax1<=w
                and 0<=ay0<=roi[1]<roi[3]<=ay1<=h):
            raise PropLayerError("edit_outside_allowed_region")
        if not isinstance(lower_body_lock_y,int) or roi[3]>=lower_body_lock_y:
            raise PropLayerError("edit_intersects_locked_lower_body")
        for rect in protected_regions:
            if len(rect)!=4:raise PropLayerError("invalid_protected_region")
            rx0,ry0,rx1,ry1=rect
            if rx0<roi[2] and rx1>roi[0] and ry0<roi[3] and ry1>roi[1]:
                raise PropLayerError("edit_intersects_protected_region")
        if min(px,py)<0 or px+planned_w>=w or py+planned_h>=h:
            raise PropLayerError("target_prop_out_of_frame")
        # Hands must start near the two edges of the detector-grounded prop.
        right, left=hands
        right_center=sum(p[0] for p in right)/len(right)
        left_center=sum(p[0] for p in left)/len(left)
        if not (right_center<cx<left_center):
            raise PropLayerError("hands_not_on_opposite_object_edges")
        if max(abs(right_center-x0),abs(left_center-x1))>object_width*.3:
            raise PropLayerError("hand_prop_attribution_ambiguous")
    except (KeyError,TypeError,IndexError,OverflowError) as err:
        raise PropLayerError("pose_or_box_incomplete") from err

    baseline=baseline.convert("RGB")
    generated=generated.convert("RGB")
    # Restore old garment only in the independently authorized area where the
    # overlarge map occluded it; keep outside pixels from the generated frame.
    mask=Image.new("L",(w,h),0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (roi[0],roi[1],roi[2]-1,roi[3]-1),radius=14,fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(6))
    result=Image.composite(baseline,generated,mask)

    # Keep map-specific text/roads from the actual generated paper layer.
    map_interior=(round(x0+8),round(y0+3),round(x1-8),round(y1-3))
    if map_interior[2]-map_interior[0]<16 or map_interior[3]-map_interior[1]<12:
        raise PropLayerError("map_interior_unobservable")
    paper=generated.crop(map_interior).resize(
        (planned_w,planned_h),Image.Resampling.LANCZOS)
    result.paste(paper,(px,py))

    palm_evidence=[]
    for label,pts,edge in (("right",right,px),("left",left,px+planned_w)):
        hx0=min(p[0] for p in pts);hx1=max(p[0] for p in pts)
        hy0=min(p[1] for p in pts);hy1=max(p[1] for p in pts)
        rect=(int(hx0-5),int(hy0-5),int(hx1+6),int(hy1+6))
        patch=generated.crop(rect)
        shift=round(edge-(hx0+hx1)/2)
        tx=rect[0]+shift
        ty=int(round(cy-(hy0+hy1)/2+rect[1]))
        if not (roi[0]<=tx and tx+patch.width<roi[2]
                and roi[1]<=ty and ty+patch.height<roi[3]):
            raise PropLayerError("transformed_hands_outside_roi")
        pmask=Image.new("L",patch.size,0)
        ImageDraw.Draw(pmask).ellipse((2,1,patch.width-3,patch.height-2),fill=255)
        pmask=pmask.filter(ImageFilter.GaussianBlur(2))
        result.paste(patch,(tx,ty),pmask)
        palm_evidence.append({"hand":label,"source_bbox":rect,"target_origin":[tx,ty]})

    # Feather is never authorized to affect pixels outside the exact ROI.
    candidate=np.asarray(result).copy()
    original=np.asarray(generated)
    unedited=np.ones((h,w),dtype=bool)
    unedited[roi[1]:roi[3],roi[0]:roi[2]]=False
    candidate[unedited]=original[unedited]
    assert np.array_equal(candidate[unedited],original[unedited])
    result=Image.fromarray(candidate,"RGB")
    changed=int(np.count_nonzero(np.any(candidate!=original,axis=2)))
    return result, {
        "status":"shadow_not_full_scene_qa",
        "observed_prior_width_px":round(object_width,3),
        "planned_width_px":planned_w,
        "source_shoulder_span_px":round(span,3),
        "planned_ratio":round(planned_w/span,4),
        "authorized_roi":list(roi),
        "protected_pixels_identical":int(unedited.sum()),
        "changed_pixels":changed,
        "hands":palm_evidence,
        "note":"2D placement; independent post-composite object/contact/wardrobe QA mandatory",
    }
