"""Independent COCO-18 pose geometry checks, no image-generation dependencies.

DWPose guide and rendered candidate are compared by anatomical bone angles,
not raw pixel locations. Matching a skeleton is NOT proof of touching a wall.
"""
from __future__ import annotations
import math

REQUIRED=(1,2,4,5,7,8,9,10,11,12,13)

def people_from_dwp_json(raw):
    frame=raw[0] if isinstance(raw,list) and raw else raw
    if not isinstance(frame,dict):return []
    return frame.get("people") or []

def joints(person):
    vec=(person or {}).get("pose_keypoints_2d") or []
    if len(vec)<54:return None
    return [(float(vec[i]),float(vec[i+1]),float(vec[i+2]))
            for i in range(0,54,3)]

def _middle(p,q):
    return ((p[0]+q[0])/2,(p[1]+q[1])/2)

def _angle(a,b):
    return math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))

def _delta(a,b):
    return abs((a-b+180)%360-180)

def inspect_approved_pose(reference_json,candidate_json):
    expected=people_from_dwp_json(reference_json)
    actual=people_from_dwp_json(candidate_json)
    if len(expected)!=1 or len(actual)!=1:
        return {"verified":False,"reason":"expected_one_detected_person",
                "reference_people":len(expected),"candidate_people":len(actual)}
    ref=joints(expected[0]);cand=joints(actual[0])
    if ref is None or cand is None:
        return {"verified":False,"reason":"missing_body_keypoints"}
    absent=[i for i in REQUIRED if ref[i][2]<.25 or cand[i][2]<.25]
    if absent:
        return {"verified":False,"reason":"missing_required_joints","indices":absent}
    rhips=_middle(ref[8],ref[11]);chips=_middle(cand[8],cand[11])
    comparisons={
        "torso":(_angle(ref[1],rhips),_angle(cand[1],chips),35),
        "right_arm":(_angle(ref[2],ref[4]),_angle(cand[2],cand[4]),45),
        "left_arm":(_angle(ref[5],ref[7]),_angle(cand[5],cand[7]),45),
        "right_leg":(_angle(ref[8],ref[10]),_angle(cand[8],cand[10]),45),
        "left_leg":(_angle(ref[11],ref[13]),_angle(cand[11],cand[13]),45),
    }
    deltas={key:round(_delta(reference,actual),1)
            for key,(reference,actual,limit) in comparisons.items()}
    failures=[key for key,(_,_,limit) in comparisons.items() if deltas[key]>limit]
    return {"verified":not failures,"reason":"geometry_match" if not failures
            else "geometry_mismatch","angle_deltas_deg":deltas,
            "failed_parts":failures,"note":"Geometry only; wall contact is not proven"}

if __name__=="__main__":
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description="Compare detected DWPose joints (no image generation)")
    p.add_argument("reference_json");p.add_argument("candidate_json")
    args=p.parse_args()
    a=json.loads(Path(args.reference_json).read_text())
    b=json.loads(Path(args.candidate_json).read_text())
    result=inspect_approved_pose(a,b)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["verified"] else 1)
