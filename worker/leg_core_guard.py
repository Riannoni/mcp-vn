"""Additional fail-closed garment-core protection for stationary actor edits.

Prevents gross alteration of the thigh garment when replacing hands/props.
This is NOT full wardrobe QA, pose or physical contact validation.
"""
from __future__ import annotations

from math import isfinite
from PIL import Image, ImageDraw


class LegCoreError(ValueError):
    pass


def check_thigh_cores(edit_mask, source_pose, principal_index):
    if not isinstance(edit_mask, Image.Image) or not isinstance(source_pose,dict):
        raise LegCoreError("missing_source_or_mask")
    if isinstance(principal_index,bool) or not isinstance(principal_index,int):
        raise LegCoreError("ambiguous_principal_index")
    try:
        width=source_pose["canvas_width"];height=source_pose["canvas_height"]
        if (not isinstance(width,int) or not isinstance(height,int) or
                min(width,height)<128 or edit_mask.size!=(width,height)):
            raise ValueError("invalid_canvas")
        people=source_pose["people"]
        if not 0<=principal_index<len(people):
            raise ValueError("ambiguous_principal")
        body=people[principal_index]["pose_keypoints_2d"]
        if not isinstance(body,(list,tuple)) or len(body)!=54:
            raise ValueError("unexpected_joint_layout")
        def joint(index):
            x,y,confidence=map(float,body[index*3:index*3+3])
            if (not all(isfinite(v) for v in (x,y,confidence)) or confidence<.65
                or not (0<=x<width and 0<=y<height)):
                raise ValueError("joint_unobservable")
            return x,y
        hips=[joint(i) for i in (8,11)]
        knees=[joint(i) for i in (9,12)]
        hip_distance=abs(hips[1][0]-hips[0][0])
        if hip_distance<width*.025 or hip_distance>width*.35:
            raise ValueError("implausible_hip_span")
        for hip,knee in zip(hips,knees):
            if knee[1]-hip[1]<height*.055:
                raise ValueError("not_observed_standing_thigh")
    except (KeyError,TypeError,ValueError,IndexError,OverflowError) as exc:
        raise LegCoreError("thigh_core_pose_unobservable") from exc
    # Use a conservative pose-derived central corridor. Protecting an entire
    # pant silhouette requires a separate reliable segmentation model.
    corridor=max(7,round(hip_distance*.16))
    immutable=Image.new("L",(width,height),0)
    draw=ImageDraw.Draw(immutable)
    for hip,knee in zip(hips,knees):
        draw.line((round(hip[0]),round(hip[1]),round(knee[0]),round(knee[1])),
                  fill=255,width=corridor)
        for x,y in (hip,knee):
            radius=max(3,corridor//2)
            draw.ellipse((round(x-radius),round(y-radius),round(x+radius),round(y+radius)),fill=255)
    editable=edit_mask.convert("L")
    overlap=Image.composite(editable,Image.new("L",editable.size),immutable)
    if overlap.getextrema()[1]>0:
        raise LegCoreError("non_target_thigh_garment_editable")
    return {"status":"source_pose_thigh_cores_locked",
            "conservative_lock_pixels":immutable.histogram()[255],
            "corridor_width_px":corridor,
            "evidence":"bilateral_hip_to_knee_source_keypoints",
            "limit":"centerline_core_only_not_full_outfit_verification"}
