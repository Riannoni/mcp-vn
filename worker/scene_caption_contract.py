"""Lightweight deterministic vetoes for strong contradictions in VLM scene captions."""
import re
from wardrobe_contract import wants_unclothed, clothing_alignment
from scene_action_contract import resolve_scene_action

_EXTRA_PERSON=re.compile(
    r"\b(?:another (?:person|woman|man|adult|figure|stands|is)|"
    r"two (?:people|persons|women|men|adults)|"
    r"second (?:person|woman|man|adult|figure))\b",re.I)

_EXPLICIT_SOLO=re.compile(
    r"\b(?:(?:only|just|exactly)\s+(?:one|a|single)|"
    r"(?:a|one)\s+(?:single|lone))\s+"
    r"(?:adult\s+)?(?:person|people|man|woman|adult|figure|character)\b",
    re.I)

def caption_asserts_single_person(caption):
    """Only positive SOLO assertions count; 'a man with a woman' is not solo."""
    return bool(_EXPLICIT_SOLO.search(str(caption or "")))

def insufficient_scene_caption(caption):
    """A bare count such as 'Two.' is not evidence of an accurate scene."""
    words=re.findall(r"[a-zA-Z]+",str(caption or ""))
    return len(words)<8

# A caption may contrast the wall with a ground surface ("hands on wall,
# not pavement"). Remove only explicitly negated ground targets before
# searching for affirmative hands-to-ground contradictions. A later positive
# mention of hands on the ground must still veto the scene.
_NEGATED_GROUND_TARGET=re.compile(
    r"\b(?:not|never|rather\s+than|instead\s+of)\s+"
    r"(?:(?:on|onto|against|touching)\s+)?(?:the\s+)?"
    r"(?:ground|paving|pavement|street)\b",re.I)


def scene_action_conflicts(characters,caption,narrator_prompt):
    """Veto clear contradictions between a requested wall brace and actual pose.

    Only assert a failure for an explicit observation, not VLM silence.
    """
    people=characters if isinstance(characters,list) else []
    if len(people)!=1 or not caption:
        return []
    intended=str(narrator_prompt or "").lower()
    pose=str(people[0].get("pose","")).lower()
    wants_brace=resolve_scene_action({
        "composition":"neural_story","characters":people,
        "prompt":narrator_prompt
    })["required"]
    if not wants_brace:
        return []
    desc=str(caption).lower()
    if re.search(r"(?<![a-z])(?:lying|laying|reclining|crawling|sitting|kneeling|crouching|squatting)(?![a-z])",desc):
        return ["CG physical pose contradicts intended standing wall contact"]
    ground_evidence=_NEGATED_GROUND_TARGET.sub("",desc)
    if re.search(r"(?<![a-z])(?:hand|hands|elbow|elbows)(?![a-z]).{0,25}"
                 r"(?<![a-z])(?:ground|paving|pavement|street)(?![a-z])",ground_evidence):
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
