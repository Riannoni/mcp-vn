"""Shadow-only geometry: source-attributed object width vs actor shoulder span.

Requires independently detected bounding box and a typed, explicit max ratio.
Only 2-D projected geometry is measured. PLAUSIBLE is not full visual QA.
"""
from __future__ import annotations
from math import isfinite

def _unknown(reason):
    return {"verdict":"unobservable", "reason":reason}

def assess(frame, principal_index, object_boxes, detector_size, *,
           max_object_to_shoulder_ratio, view, same_depth):
    if view != "front" or same_depth is not True:
        return _unknown("view_or_depth_not_supported")
    if isinstance(max_object_to_shoulder_ratio, bool) or not isinstance(max_object_to_shoulder_ratio,(int,float)) or not isfinite(max_object_to_shoulder_ratio) or max_object_to_shoulder_ratio <= 0:
        return _unknown("typed_scale_constraint_missing")
    if not isinstance(frame,dict) or isinstance(principal_index,bool) or not isinstance(principal_index,int):
        return _unknown("source_pose_missing_or_actor_unattributed")
    try:
        w,h=frame["canvas_width"],frame["canvas_height"]
        dw,dh=detector_size
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) or v<=0 for v in (w,h,dw,dh)):
            raise ValueError()
        if w<128 or h<128:
            raise ValueError()
        persons=frame["people"]
        if not 0<=principal_index<len(persons):
            raise ValueError()
        vec=persons[principal_index]["pose_keypoints_2d"]
        if not isinstance(vec,(tuple,list)) or len(vec)!=54:
            raise ValueError()
        shoulders=[]
        for k in (2,5): # OpenPose18 right/left shoulder
            x,y,c=map(float,vec[3*k:3*k+3])
            if not all(isfinite(v) for v in (x,y,c)) or c<.65 or not (0<=x<w and 0<=y<h):
                raise ValueError()
            shoulders.append((x,y))
        shoulder_width=abs(shoulders[0][0]-shoulders[1][0])
        if shoulder_width < .035*w or abs(shoulders[0][1]-shoulders[1][1])>.15*h:
            raise ValueError()
    except (ValueError,TypeError,KeyError,IndexError,OverflowError):
        return _unknown("shoulders_unobservable_or_ambiguous")
    if not isinstance(object_boxes,(tuple,list)) or len(object_boxes)!=1:
        return _unknown("object_detection_missing_or_ambiguous")
    try:
        box=object_boxes[0]
        if not isinstance(box,(tuple,list)) or len(box)!=4:
            raise ValueError()
        x0,y0,x1,y1=map(float,box)
        if not all(isfinite(v) for v in (x0,y0,x1,y1)) or not (0<=x0<x1<=dw and 0<=y0<y1<=dh):
            raise ValueError()
    except (ValueError,TypeError,OverflowError):
        return _unknown("invalid_grounded_object_box")
    object_width=(x1-x0)*w/dw
    ratio=object_width/shoulder_width
    # Do not call a geometrically plausible ratio a verification of scene facts.
    return {"verdict":"violated" if ratio>max_object_to_shoulder_ratio else "plausible",
            "reason":"projected_object_too_wide" if ratio>max_object_to_shoulder_ratio else "projected_size_within_typed_limit",
            "projected_ratio":round(ratio,4),
            "required_max_ratio":max_object_to_shoulder_ratio,
            "method":"independent_bbox_over_detected_front_view_shoulder_width",
            "note":"2-D only; do not certify 3-D physical size or contact"}
