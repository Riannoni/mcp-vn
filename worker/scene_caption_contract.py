"""Lightweight deterministic vetoes for strong contradictions in VLM scene captions."""
import re
from wardrobe_contract import wants_unclothed, clothing_alignment

_EXTRA_PERSON=re.compile(
    r"\b(?:another (?:person|woman|man|adult|figure|stands|is)|"
    r"two (?:people|persons|women|men|adults)|"
    r"second (?:person|woman|man|adult|figure))\b",re.I)

def insufficient_scene_caption(caption):
    """A bare count such as 'Two.' is not evidence of an accurate scene."""
    words=re.findall(r"[a-zA-Z]+",str(caption or ""))
    return len(words)<8

def scene_action_conflicts(characters,caption,narrator_prompt):
    """Veto clear contradictions between a requested wall brace and actual pose.

    Only assert a failure for an explicit observation, not VLM silence.
    """
    people=characters if isinstance(characters,list) else []
    if len(people)!=1 or not caption:
        return []
    intended=str(narrator_prompt or "").lower()
    pose=str(people[0].get("pose","")).lower()
    wants_brace=(
        ("wall" in intended or "masonry" in intended) and
        ("lean" in intended or "brac" in intended or "palm" in intended or
         "lean" in pose)
    )
    if not wants_brace:
        return []
    desc=str(caption).lower()
    if re.search(r"(?<![a-z])(?:lying|laying|reclining|crawling|sitting)(?![a-z])",desc):
        return ["CG physical pose contradicts intended standing wall contact"]
    if re.search(r"(?<![a-z])(?:hand|hands|elbow|elbows)(?![a-z]).{0,25}"
                 r"(?<![a-z])(?:ground|paving|pavement|street)(?![a-z])",desc):
        return ["CG hands are on the ground instead of on the required wall"]
    return []


def scene_caption_conflicts(characters,caption):
    people=characters if isinstance(characters,list) else []
    desc=str(caption or "")
    reasons=[]
    if insufficient_scene_caption(desc):
        reasons.append("VLM did not describe CG contents well enough to verify the scene")
    if len(people)==1 and _EXTRA_PERSON.search(desc):
        reasons.append("Neural CG contains an additional principal figure according to VLM")
    if len(people)==1 and wants_unclothed(people[0].get("outfit","")):
        # A definite visible clothing contradiction is evidence; silence,
        # ambiguous framing or uncertain captions are not.
        if clothing_alignment(desc)=="failed":
            reasons.append("Neural CG wardrobe contradicts requested unclothed state")
    return reasons
