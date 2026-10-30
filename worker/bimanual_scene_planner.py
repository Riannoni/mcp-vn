"""Generic fail-closed bimanual scene preflight, shadow only.

Derives a prop target, hand pose and bounded editable mask from independently
attributed source OpenPose18 keypoints; no game-specific pixel coordinates.
Does NOT establish final physical grip, actor identity or wardrobe accuracy.
"""
from __future__ import annotations
from copy import deepcopy
from math import isfinite
from PIL import Image, ImageDraw, ImageFilter, ImageOps


class BimanualPlanError(ValueError):
    pass


def plan_bimanual(frame, principal_index, *, object_kind, zone,
                  width_ratio, aspect_ratio, view="front", same_depth=True):
    if view!="front" or same_depth is not True:
        raise BimanualPlanError("unsupported_view_or_depth")
    if not isinstance(object_kind,str) or not object_kind.strip() or len(object_kind)>80:
        raise BimanualPlanError("object_kind_missing")
    if zone not in ("chest","waist"):
        raise BimanualPlanError("unsupported_zone")
    if any(isinstance(q,bool) or not isinstance(q,(float,int)) or
           not isfinite(q) for q in (width_ratio,aspect_ratio)):
        raise BimanualPlanError("typed_scale_missing")
    if not .30<=width_ratio<=.95 or not .25<=aspect_ratio<=.95:
        raise BimanualPlanError("target_geometry_out_of_range")
    if not isinstance(frame,dict) or isinstance(principal_index,bool) or not isinstance(principal_index,int):
        raise BimanualPlanError("source_attribution_missing")
    try:
        w,h=frame["canvas_width"],frame["canvas_height"]
        if not isinstance(w,int) or not isinstance(h,int) or min(w,h)<128:
            raise ValueError("invalid canvas")
        persons=frame["people"]
        if not 0<=principal_index<len(persons):
            raise ValueError("principal ambiguous")
        principal=persons[principal_index]
        body=list(map(float,principal["pose_keypoints_2d"]))
        if len(body)!=54:raise ValueError("unexpected pose layout")
        def joint(i):
            x,y,c=body[i*3:i*3+3]
            if not all(isfinite(z) for z in (x,y,c)) or c<.75 or not (0<=x<w and 0<=y<h):
                raise ValueError("missing joint")
            return x,y
        neck,r_sh,l_sh,r_hip,l_hip=[joint(i) for i in (1,2,5,8,11)]
        if not (r_sh[0]<l_sh[0] and r_hip[0]<l_hip[0]):
            raise ValueError("front attribution invalid")
        span=l_sh[0]-r_sh[0]
        if not .045*w<span<.24*w:
            raise ValueError("shoulder separation implausible")
        # Check that the body is seen front-on, not very strongly oblique.
        if abs(r_sh[1]-l_sh[1])>.1*h:
            raise ValueError("camera not frontal")
        hip_y=(r_hip[1]+l_hip[1])/2
        if hip_y-neck[1]<.12*h:
            raise ValueError("torso not observable")
        for key in ("hand_left_keypoints_2d","hand_right_keypoints_2d"):
            vals=list(map(float,principal[key]))
            if len(vals)!=63 or sum(vals[i*3+2]>=.55 for i in range(21))<17:
                raise ValueError("stale source hands unobservable")
    except (KeyError,IndexError,TypeError,ValueError,OverflowError) as e:
        raise BimanualPlanError("observed_source_pose_incomplete") from e
    mid_x=(r_sh[0]+l_sh[0])/2
    frac=.54 if zone=="chest" else .85
    mid_y=neck[1]+frac*(hip_y-neck[1])
    width=round(span*width_ratio)
    height=round(width*aspect_ratio)
    bbox=[round(mid_x-width/2),round(mid_y-height/2),
          round(mid_x+width/2),round(mid_y+height/2)]
    if bbox[0]<=0 or bbox[1]<=0 or bbox[2]>=w or bbox[3]>=hip_y:
        raise BimanualPlanError("target_intersects_lower_body_or_canvas")
    hands={"right":(bbox[0],round(mid_y)), "left":(bbox[2],round(mid_y))}
    source_pose=deepcopy(frame)
    out=source_pose["people"][principal_index]["pose_keypoints_2d"]
    def setpoint(j,x,y):
        out[j*3:j*3+3]=[float(x),float(y),.99]
    for sign,shoulder,elbow,wrist,target in (
        (-1,r_sh,3,4,hands["right"]),
        (1,l_sh,6,7,hands["left"])):
        elbow_x=shoulder[0]+sign*span*.26
        elbow_y=shoulder[1]+.69*(mid_y-shoulder[1])
        setpoint(elbow,elbow_x,elbow_y)
        setpoint(wrist,*target)
    return {"version":1,"action":"bimanual_hold","object_kind":object_kind,
            "zone":zone,"view":"front","same_depth":True,
            "principal_index":principal_index,"source_canvas":[w,h],
            "prop_bbox":bbox,"prop_width_over_shoulders":round(width/span,4),
            "hands":hands,"source_pose":source_pose,
            "status":"geometry_plan_not_visual_qa"}


def make_edit_mask(frame, plan):
    """Build inverse-alpha Comfy mask from source arms, stale hands, new wrists.

    Strict anatomy guard must independently validate the returned mask.
    A mask that cannot cover stale hands without touching immutable trousers
    must be rejected, never silently weakened.
    """
    if not isinstance(plan,dict) or plan.get("status")!="geometry_plan_not_visual_qa":
        raise BimanualPlanError("unverified_plan")
    try:
        w,h=plan["source_canvas"]
        index=plan["principal_index"]
        actor=frame["people"][index]
        pose=actor["pose_keypoints_2d"]
        b=plan["prop_bbox"]
        width=abs(frame["people"][index]["pose_keypoints_2d"][5*3]-
                  frame["people"][index]["pose_keypoints_2d"][2*3])
        if w!=frame["canvas_width"] or h!=frame["canvas_height"] or not 0<b[0]<b[2]<w or not 0<b[1]<b[3]<h:
            raise ValueError("canvas/bbox mismatch")
        edit=Image.new("L",(w,h),0);d=ImageDraw.Draw(edit)
        def srcjoint(j):return (float(pose[3*j]),float(pose[3*j+1]))
        # Include entirely observed source hands and their original sleeves.
        for side,elbow,old_wrist,hand_name in (
             ("right",3,4,"hand_right_keypoints_2d"),
             ("left",6,7,"hand_left_keypoints_2d")):
            points=actor[hand_name]
            valid=[(float(points[3*i]),float(points[3*i+1])) for i in range(21)
                   if float(points[3*i+2])>=.55]
            if len(valid)<17:raise ValueError("source hands not observed")
            a=srcjoint(elbow);old=srcjoint(old_wrist);new=plan["hands"][side]
            thickness=max(12,round(width*.24))
            d.line((a,old),fill=255,width=thickness)
            d.line((a,new),fill=255,width=thickness)
            rad=max(9,round(width*.15))
            for x,y in (old,new):
                d.ellipse((x-rad,y-rad,x+rad,y+rad),fill=255)
            padding=max(8,round(width*.12))
            d.rectangle((min(x for x,y in valid)-padding,min(y for x,y in valid)-padding,
                         max(x for x,y in valid)+padding,max(y for x,y in valid)+padding),fill=255)
        d.rounded_rectangle((b[0]-5,b[1]-5,b[2]+5,b[3]+5),
                            radius=max(3,round(width*.08)),fill=255)
        edit=edit.filter(ImageFilter.GaussianBlur(2))
        # Conservative safety locks, independent source pose only.
        d=ImageDraw.Draw(edit)
        neck_y=pose[1*3+1]
        d.rectangle((0,0,w,round(neck_y+4)),fill=0)
        rhip=(pose[8*3],pose[8*3+1]);lhip=(pose[11*3],pose[11*3+1])
        rknee=(pose[9*3],pose[9*3+1]);lknee=(pose[12*3],pose[12*3+1])
        hip_span=abs(lhip[0]-rhip[0])
        corridor=max(7,round(hip_span*.16))+6
        for hip,knee in ((rhip,rknee),(lhip,lknee)):
            d.line((hip,knee),fill=0,width=corridor)
            for x,y in (hip,knee):
                d.ellipse((x-corridor/2,y-corridor/2,
                           x+corridor/2,y+corridor/2),fill=0)
        # Freeze knees-to-bottom entirely; stricter than existing shin guard.
        d.rectangle((0,round(min(rknee[1],lknee[1])),w,h),fill=0)
        rgba=Image.new("RGBA",(w,h),(0,0,0,255))
        rgba.putalpha(ImageOps.invert(edit))
        return rgba
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as e:
        raise BimanualPlanError("cannot_build_safe_edit_mask") from e
