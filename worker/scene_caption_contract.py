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

def scene_caption_conflicts(characters,caption):
    people=characters if isinstance(characters,list) else []
    desc=str(caption or "")
    reasons=[]
    if insufficient_scene_caption(desc):
        reasons.append("VLM did not describe CG contents well enough to verify the scene")
    if len(people)==1 and _EXTRA_PERSON.search(desc):
        reasons.append("Neural CG contains an additional principal figure according to VLM")
    if len(people)==1 and wants_unclothed(people[0].get("outfit","")):
        # Relax for explicit NSFW requests: do not hard-reject on VLM wardrobe guess
        if clothing_alignment(desc)=="failed" and not any(w in desc.lower() for w in ["nude","naked","unclothed","bare","nsfw"]):
            reasons.append("Neural CG wardrobe contradicts requested unclothed state")
    return reasons
