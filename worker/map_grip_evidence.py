"""Non-authoritative two-hand map-edge relation evidence from DWPose+Florence.

2-D fingertip proximity is NOT a proof of physical grip. A separated hand
rules out this specific apparent two-handed map grip, and must not be accepted.
"""
from __future__ import annotations
import re

MAP=re.compile(r'\b(?:street |paper |folded |unfolded )?map\b',re.I)
HOLD=re.compile(r'\b(?:hold(?:s|ing)?|grasp(?:s|ing)?|grip(?:s|ping)?|show(?:s|ing)?)\b',re.I)

def evaluate(frame,principal_index,map_boxes,detector_size,caption):
    unseen=lambda reason:{'verdict':'unobservable','reason':reason}
    if not isinstance(frame,dict):return unseen('pose_missing')
    try:
        w=float(frame['canvas_width']);h=float(frame['canvas_height'])
        dw,dh=map(float,detector_size)
        if min(w,h,dw,dh)<=0:raise ValueError
    except (ValueError,TypeError,KeyError):return unseen('dimensions_invalid')
    people=frame.get('people') or []
    if not isinstance(principal_index,int) or not 0<=principal_index<len(people):
        return unseen('principal_ambiguous')
    person=people[principal_index]
    centers=[]
    for side in ('hand_left_keypoints_2d','hand_right_keypoints_2d'):
        a=person.get(side) or []
        if len(a)!=63:return unseen('hand_landmarks_missing')
        try:pts=[(float(a[i*3])/w,float(a[i*3+1])/h,float(a[i*3+2])) for i in range(21)]
        except (TypeError,ValueError):return unseen('invalid_hand_landmarks')
        if sum(z>=.5 for x,y,z in pts)<17:return unseen('hand_landmarks_low_confidence')
        tips=[pts[i] for i in (4,8,12,16,20)]
        if any(z<.5 for x,y,z in tips):return unseen('fingertips_not_visible')
        centers.append((sum(x for x,y,z in tips)/5,sum(y for x,y,z in tips)/5))
    caption=str(caption or '')
    if not MAP.search(caption) or not HOLD.search(caption):return unseen('independent_caption_no_two_hand_map')
    candidates=[]
    for b in map_boxes or []:
        if not isinstance(b,(list,tuple)) or len(b)!=4:continue
        try:x0,y0,x1,y1=map(float,b)
        except (ValueError,TypeError):continue
        if not (0<=x0<x1<=dw and 0<=y0<y1<=dh):continue
        x0/=dw;x1/=dw;y0/=dh;y1/=dh
        if not (.07<=x1-x0<=.75 and .05<=y1-y0<=.5):continue
        candidates.append((x0,y0,x1,y1))
    if len(candidates)!=1:return unseen('map_bbox_ambiguous')
    x0,y0,x1,y1=candidates[0]
    left,right=sorted(centers)
    if right[0]-left[0]<.09:return unseen('hands_not_on_opposite_edges')
    edge=max(.022,(x1-x0)*.2)
    def reaches(c,target):
        x,y=c
        return abs(x-target)<=edge and y0-.02<=y<=y1+.018
    if not reaches(left,x0) or not reaches(right,x1):
        return {**unseen('one_or_both_hands_not_on_map_edges'),
          'hand_centers':[[round(x,4),round(y,4)] for x,y in centers],
          'map_box':[round(v,4) for v in candidates[0]]}
    return {'verdict':'plausible','reason':'two_opposite_edges_hand_landmarks_caption',
      'note':'2-D corroboration only; physical grip requires further review'}
