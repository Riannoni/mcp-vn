"""Explicit principal-actor regions for identity conditioning.

Never silently drop a named principal. A single pass is intentionally bounded
to four anchored faces on the current 16GB GPU; beyond that we must use a
staged multi-pass workflow, not misrepresent a partial identity render as done.
Bystanders are not named principals and must not consume face anchors.
"""
from __future__ import annotations

from engine_policy import read_engine_contract
MAX_CG_FACE_ANCHORS=read_engine_contract()['render']['max_anchored_principals_per_pass']

def region_for_actor(index,count,region=None):
    if not 1<=count<=MAX_CG_FACE_ANCHORS:
        raise ValueError(
            f"CG has {count} named principals; only 1-{MAX_CG_FACE_ANCHORS} "
            "individual face anchors supported in a single pass. "
            "Use a staged scene workflow for larger principal casts."
        )
    if not 0<=index<count:
        raise ValueError("actor index outside declared principal cast")
    if region is not None:
        if not isinstance(region,(list,tuple)) or len(region)!=4:
            raise ValueError("actor_region must be [left,top,width,height] normalized")
        x,y,w,h=map(float,region)
        if not (0<=x<1 and 0<=y<1 and 0<w<=1 and 0<h<=1 and
                x+w<=1.00001 and y+h<=1.00001):
            raise ValueError("actor_region outside normalized image")
        return x,y,x+w,y+h
    if count==1:
        return 0.015,0.04,0.985,0.96
    # Provisional equally spaced foreground grouping ONLY. Complex blocking
    # needs the narrator to supply explicit actor_region coordinates.
    span=1/count
    margin=min(0.018,span*.12)
    x0=max(.0,index*span-margin)
    x1=min(1.,(index+1)*span+margin)
    return x0,.04,x1,.96

def assert_cast_supported(actors):
    n=len(actors)
    if not 1<=n<=MAX_CG_FACE_ANCHORS:
        raise ValueError(
            f"Cannot anchor {n} main characters in one CG; "
            f"current safe maximum is {MAX_CG_FACE_ANCHORS}, "
            "additional background extras are not counted."
        )
    for i,actor in enumerate(actors):
        region_for_actor(i,n,actor.get("actor_region"))
    return n
