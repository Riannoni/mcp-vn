"""Non-authoritative, image-level, bilateral framing evidence for arches.

Whole-frame caption and whole-frame CLIP notoriously ignore side masonry.
This is a supplemental observation, not a release gate or `verified` result.
Both crops and text contrasts are fixed before processing each frame. It
cannot certify a *complete* arch, motion underneath it, or actor continuity.
"""
from __future__ import annotations
import math

ARCH_TEXT='The foreground stone of a large medieval arched gateway frames this town street from above and from both sides.'
OPEN_TEXT='The sky above the open medieval town street has no nearby arch or stone gateway covering it.'


def bilateral_regions(size):
    try:
        w,h=map(int,size)
        if w<256 or h<192:raise ValueError
    except (ValueError,TypeError):return None
    return {'upper_left':(0,0,round(w*.36),round(h*.65)),
            'upper_right':(round(w*.64),0,w,round(h*.65))}


def summarize_side_logits(logits):
    if not isinstance(logits,dict) or set(logits)!={'upper_left','upper_right'}:
        return {'verdict':'unobservable','reason':'both_side_rois_required'}
    gaps={}
    for name in ('upper_left','upper_right'):
        row=logits.get(name)
        if not isinstance(row,(tuple,list)) or len(row)!=2:
            return {'verdict':'unobservable','reason':'missing_contrast_values'}
        if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in row):
            return {'verdict':'unobservable','reason':'invalid_contrast_values'}
        gaps[name]=round(float(row[0]-row[1]),4)
    matched=all(gap>0 for gap in gaps.values())
    return {'verdict':'bilateral_arch_supported' if matched else 'unobservable',
            'reason':'both_side_arch_vs_open_contrast' if matched else 'no_bilateral_arch_contrast',
            'side_logit_gaps':gaps,
            'warning':'Not a verified stone arch: no causal link to ceiling, pose, or story action'}


def observe(image,processor,model):
    import torch
    rects=bilateral_regions(image.size)
    if not rects:return {'verdict':'unobservable','reason':'canvas_too_small'}
    scores={}
    for key,rect in rects.items():
        crop=image.convert('RGB').crop(rect)
        q=processor(text=[ARCH_TEXT,OPEN_TEXT],images=crop,return_tensors='pt',padding=True)
        with torch.inference_mode():p=model(**q).logits_per_image[0].tolist()
        scores[key]=p
    return summarize_side_logits(scores)
