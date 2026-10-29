"""Spatial evidence from independent object detector boxes, never face identity.

People, named principals and ambient extras are DISTINCT concepts. A detection
inside a principal ROI establishes a plausible spatial occupant only; it does
not tell which named character is present, or whether a hand touches anything.
"""
from __future__ import annotations
import math

PERSON={"person","man","woman","boy","girl","human"}
def intersection(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0])) * max(
        0,min(a[3],b[3])-max(a[1],b[1]))
def area(a):
    return max(0,a[2]-a[0])*max(0,a[3]-a[1])
def region(raw):
    if not isinstance(raw,(list,tuple)) or len(raw)!=4:return None
    try:x,y,w,h=map(float,raw)
    except (ValueError,TypeError):return None
    if not(0<=x<1 and 0<=y<1 and w>0 and h>0 and x+w<=1 and y+h<=1):
        return None
    return (x,y,x+w,y+h)
def boxes_from_od(detections,size):
    """Normalize bbox collection with overlap suppression and exact labels."""
    labels=detections.get("labels") or []
    raw=detections.get("bboxes") or []
    width,height=map(float,size)
    if width<=0 or height<=0:return []
    boxes=[]
    for label,b in zip(labels,raw):
        if str(label).lower().strip() not in PERSON or len(b)!=4:continue
        try:box=tuple(float(v) for v in b)
        except (TypeError,ValueError):continue
        if not all(math.isfinite(v) for v in box):continue
        x0,y0,x1,y1=box
        norm=(max(0,x0/width),max(0,y0/height),
              min(1,x1/width),min(1,y1/height))
        if area(norm)<.006:continue
        boxes.append(norm)
    # Area-first NMS prevents duplicate man/woman labels from double-counting.
    dedup=[]
    for box in sorted(boxes,key=area,reverse=True):
        if any(intersection(box,prior)/max(.00001,min(area(box),area(prior)))>.72
               for prior in dedup):
            continue
        dedup.append(box)
    return dedup[:32]

def principal_spatial_observation(people,detections,size):
    """Return no stronger than 'spatially_present'; unknown otherwise."""
    regions=[]
    for p in people:
        r=region((p or {}).get("region"))
        if r is None:
            return {"verdict":"unobservable","reason":"explicit_actor_regions_required"}
        regions.append(r)
    if not regions or len(regions)>4:
        return {"verdict":"unobservable","reason":"unsupported_cast"}
    boxes=boxes_from_od(detections,size)
    if not boxes:
        return {"verdict":"unobservable","reason":"no_reliable_person_boxes"}
    used=set();by_actor=[]
    for i,roi in enumerate(regions):
        matches=[]
        for idx,box in enumerate(boxes):
            x=(box[0]+box[2])/2;y=(box[1]+box[3])/2
            # Larger person detection and visible center inside declared ROI.
            if (area(box)>.045 and roi[0]<=x<=roi[2] and
                roi[1]<=y<=roi[3] and
                intersection(box,roi)/max(.001,area(box))>.40):
                matches.append((idx,box))
        if len(matches)!=1:
            return {"verdict":"unobservable","reason":"ambiguous_or_missing_principal_region",
                    "ambiguous_region_index":i,"detection_count":len(boxes)}
        idx,_=matches[0]
        if idx in used:
            return {"verdict":"unobservable","reason":"one_box_matches_multiple_principals"}
        used.add(idx)
        by_actor.append({"actor_index":i,"detector_index":idx})
    unassigned=[b for i,b in enumerate(boxes) if i not in used]
    return {"verdict":"spatially_present","reason":"each_region_has_distinct_person_box",
            "named_identity_verified":False,"principal_observations":by_actor,
            "ambient_detection_count":len(unassigned),
            "unassigned_large_detections":sum(area(b)>.045 for b in unassigned)}
