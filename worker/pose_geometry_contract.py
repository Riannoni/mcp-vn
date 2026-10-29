"""Independent COCO-18 pose geometry QA, separate from scene cardinality.

DWPose may return many tiny background detections in a street scene. Match
the dominant foreground body to the approved pose. Reject frames with two
similarly prominent foreground bodies; never use a small matching background
figure to explain away the pose of the principal character.

Skeleton similarity does NOT prove wall/surface contact or wardrobe.
"""
from __future__ import annotations
import math

REQUIRED=(1,2,4,5,7,8,9,10,11,12,13)


def people_from_dwp_json(raw):
    frame=raw[0] if isinstance(raw,list) and raw else raw
    if not isinstance(frame,dict):
        return []
    return frame.get("people") or []


def joints(person):
    vec=(person or {}).get("pose_keypoints_2d") or []
    if len(vec)<54:
        return None
    return [(float(vec[i]),float(vec[i+1]),float(vec[i+2]))
            for i in range(0,54,3)]


def _body_area(points):
    """Bounding area from actual detected joints, not an image-level crop."""
    if points is None:
        return 0.0
    valid=[p for p in points if p[2]>=.25]
    if len(valid)<8:
        return 0.0
    xs=[p[0] for p in valid]
    ys=[p[1] for p in valid]
    return max(0.0,max(xs)-min(xs))*max(0.0,max(ys)-min(ys))


def _middle(p,q):
    return ((p[0]+q[0])/2,(p[1]+q[1])/2)


def _angle(a,b):
    return math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))


def _delta(a,b):
    return abs((a-b+180)%360-180)


def inspect_approved_pose(reference_json,candidate_json,actor_region=None):
    """actor_region is an explicit normalized principal ROI, never inferred."""

    expected=people_from_dwp_json(reference_json)
    actual=people_from_dwp_json(candidate_json)
    if len(expected)!=1:
        return {"verified":False,"reason":"invalid_reference_people",
                "reference_people":len(expected),"candidate_people":len(actual)}
    ref=joints(expected[0])
    if ref is None:
        return {"verified":False,"reason":"missing_reference_keypoints"}
    if not actual:
        return {"verified":False,"reason":"no_detected_person",
                "candidate_people":0}

    scored=[]
    for index,person in enumerate(actual):
        body=joints(person)
        area=_body_area(body)
        scored.append((area,index,body))
    scored.sort(key=lambda row:row[0],reverse=True)
    frame=candidate_json[0] if isinstance(candidate_json,list) and candidate_json else candidate_json
    if actor_region is not None:
        try:
            x,y,w,h=map(float,actor_region)
            cw=float(frame.get("canvas_width") or 0)
            ch=float(frame.get("canvas_height") or 0)
            if not(0<=x<1 and 0<=y<1 and w>0 and h>0 and
                   x+w<=1 and y+h<=1 and cw>1 and ch>1):
                raise ValueError("invalid ROI")
            inside=[]
            for area,index,body in scored:
                valid=[(px,py) for px,py,c in (body or []) if c>=.25]
                if len(valid)<8 or area<=0:continue
                cx=(min(px for px,py in valid)+max(px for px,py in valid))/(2*cw)
                cy=(min(py for px,py in valid)+max(py for px,py in valid))/(2*ch)
                if x<=cx<=x+w and y<=cy<=y+h:inside.append((area,index,body))
            if len(inside)!=1:
                return {"verified":False,"reason":"ambiguous_principal_roi",
                        "principal_roi_matches":len(inside),
                        "candidate_people":len(actual)}
            lead_area,lead_index,cand=inside[0]
            roi_selected=True
        except (ValueError,TypeError,AttributeError):
            return {"verified":False,"reason":"invalid_principal_roi"}
    else:
        lead_area,lead_index,cand=scored[0]
        roi_selected=False
    if lead_area<=0:
        return {"verified":False,"reason":"no_complete_foreground_person",
                "candidate_people":len(actual)}
    competitor_area=max((area for area,index,_ in scored if index!=lead_index),default=0)
    relative=competitor_area/lead_area
    summary={"reference_people":1,"candidate_people":len(actual),
             "principal_index":lead_index,
             "principal_selected_by_roi":roi_selected,
             "principal_bbox_area":round(lead_area,1),
             "competing_bbox_fraction":round(relative,3)}
    # This is an ambiguity check, not a visual people counter. The separate
    # scene-count QA still determines whether background people are allowed.
    if not roi_selected and relative>=.35:
        return {"verified":False,"reason":"ambiguous_foreground_people",**summary}
    absent=[i for i in REQUIRED if ref[i][2]<.25 or cand[i][2]<.25]
    if absent:
        return {"verified":False,"reason":"missing_required_joints",
                "indices":absent,**summary}
    rhips=_middle(ref[8],ref[11])
    chips=_middle(cand[8],cand[11])
    comparisons={
        "torso":(_angle(ref[1],rhips),_angle(cand[1],chips),35),
        "right_arm":(_angle(ref[2],ref[4]),_angle(cand[2],cand[4]),45),
        "left_arm":(_angle(ref[5],ref[7]),_angle(cand[5],cand[7]),45),
        "right_leg":(_angle(ref[8],ref[10]),_angle(cand[8],cand[10]),45),
        "left_leg":(_angle(ref[11],ref[13]),_angle(cand[11],cand[13]),45),
    }
    deltas={key:round(_delta(reference,observed),1)
            for key,(reference,observed,limit) in comparisons.items()}
    failures=[key for key,(_,_,limit) in comparisons.items()
              if deltas[key]>limit]
    return {"verified":not failures,
            "reason":"geometry_match" if not failures else "geometry_mismatch",
            "angle_deltas_deg":deltas,"failed_parts":failures,
            "note":"Body geometry only; wall contact is not proven",
            **summary}


if __name__=="__main__":
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser()
    p.add_argument("reference_json");p.add_argument("candidate_json")
    args=p.parse_args()
    a=json.loads(Path(args.reference_json).read_text())
    b=json.loads(Path(args.candidate_json).read_text())
    result=inspect_approved_pose(a,b)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["verified"] else 1)
