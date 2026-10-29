"""Conservative contact geometry from DWPose wrists and an explicit target ROI.

Being near or inside a target box is only *plausible*, NEVER proof that a
hand actually touches the intended surface. A confident, large spatial gap is
negative evidence; hidden wrists or missing target geometry are unobservable.
"""
from __future__ import annotations
import math

def inspect_contact_region(pose_json,contact):
    if not isinstance(contact,dict) or not isinstance(contact.get("target_region"),list):
        return {"verdict":"unobservable","reason":"contact_target_not_localized"}
    rect=contact["target_region"]
    if (len(rect)!=4 or any(not isinstance(v,(int,float)) for v in rect)):
        return {"verdict":"unobservable","reason":"invalid_target_region"}
    x,y,w,h=map(float,rect)
    if not(0<=x<1 and 0<=y<1 and w>0 and h>0 and x+w<=1 and y+h<=1):
        return {"verdict":"unobservable","reason":"invalid_target_region"}
    frame=(pose_json[0] if isinstance(pose_json,list) and pose_json else pose_json)
    if not isinstance(frame,dict):
        return {"verdict":"unobservable","reason":"no_keypoints"}
    cw=float(frame.get("canvas_width") or 0)
    ch=float(frame.get("canvas_height") or 0)
    if not(cw>1 and ch>1):
        return {"verdict":"unobservable","reason":"missing_canvas"}
    figures=frame.get("people") or []
    # On multiple similarly prominent people, no named-person attribution.
    if len(figures)!=1:
        return {"verdict":"unobservable","reason":"ambiguous_contact_actor"}
    keypoints=figures[0].get("pose_keypoints_2d") or []
    if len(keypoints)<54:
        return {"verdict":"unobservable","reason":"missing_body_joints"}
    # COCO-18 right and left wrists indices 4 and 7.
    wrists=[]
    for idx in (4,7):
        xx,yy,confidence=map(float,keypoints[idx*3:idx*3+3])
        if confidence<.50:return {"verdict":"unobservable","reason":"occluded_wrist"}
        wrists.append((xx/cw,yy/ch))
    def dist(px,py):
        ddx=max(x-px,0,px-(x+w))
        ddy=max(y-py,0,py-(y+h))
        return math.hypot(ddx,ddy)
    distances=[dist(*point) for point in wrists]
    if min(distances)>.12:
        return {"verdict":"violated","reason":"both_visible_wrists_far_from_target",
                "min_normalized_distance":round(min(distances),3)}
    if max(distances)<=.035:
        return {"verdict":"plausible","reason":"wrists_near_target_not_contact_proof",
                "max_normalized_distance":round(max(distances),3)}
    return {"verdict":"unobservable","reason":"partial_or_ambiguous_contact_geometry",
            "max_normalized_distance":round(max(distances),3)}
