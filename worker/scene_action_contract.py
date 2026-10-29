"""Deterministic, fail-closed checks for narrated wall-contact actions.

The small VLM describes an image; it does not decide what the story intended.
Keep this contract specific to explicit two-hand wall-bracing scenes.
"""
from __future__ import annotations
import re

WALL = re.compile(r"\b(?:wall|masonry|stonework|brickwork)\b", re.I)
HANDS = re.compile(r"\b(?:both\s+(?:palms|hands)|two\s+(?:palms|hands))\b", re.I)
LEAN = re.compile(r"\b(?:leans?|leaning|bends?|bending|bent|braced?|hinges?|hinged)\b", re.I)
NEGATIVE_POSE = re.compile(
    r"\b(?:lying|laying|reclining|crawling|kneeling|sitting|"
    r"on all fours|hands and knees|lying down|on the floor|on the ground)\b",re.I)
HANDS_GROUND = re.compile(
    r"\b(?:hands?|palms?|elbows?)\b.{0,30}"
    r"\b(?:resting|placed|pressed|planted|touch(?:ing)?|braced|on)\b"
    r".{0,30}\b(?:ground|floor|paving|pavement|cobblestones|road|street)\b",
    re.I)
WALL_TOUCH = re.compile(
    r"\b(?:hands?|palms?)\b.{0,55}"
    r"\b(?:against|on|onto|touch(?:ing)?|press(?:ed|ing)?|braced|"
    r"rest(?:ing)?|planted|placed)\b"
    r".{0,35}\b(?:wall|masonry|stonework|brickwork)\b"
    r"|\b(?:wall|masonry|stonework|brickwork)\b.{0,45}"
    r"\b(?:touch(?:ing)?|press(?:ed|ing)?|braced|against|on)\b"
    r".{0,35}\b(?:hands?|palms?)\b",
    re.I)
BOTH_OBSERVED = re.compile(r"\b(?:both|two)\b.{0,35}\b(?:hands?|palms?)\b"
                           r"|\b(?:hands?|palms?)\b.{0,35}\b(?:both|two)\b",re.I)
SUPPORT = re.compile(
    r"\b(?:standing|stands?|feet|foot|straight legs?|legs? straight|"
    r"legs? planted|on (?:her|his|their|both) feet)\b",re.I)
FORWARD = re.compile(
    r"\b(?:lean(?:s|ing)?|bend(?:s|ing)?|bent|hing(?:e|es|ed))\b"
    r".{0,35}\b(?:forward|toward|towards|wall|waist|hips?)\b"
    r"|\b(?:torso|body)\b.{0,30}\b(?:forward|bent|leaning|"
    r"horizontal|hinged)\b",re.I)
UNCERTAIN = re.compile(r"\b(?:unclear|cannot tell|can't see|not visible|"
                       r"hidden|not possible to see)\b",re.I)


def wall_brace_required(spec):
    if (spec or {}).get("composition")!="neural_story":
        return False
    actors=(spec or {}).get("characters") or []
    if len(actors)!=1:
        return False
    prompt=str((spec or {}).get("prompt") or "")
    return bool(WALL.search(prompt) and HANDS.search(prompt) and LEAN.search(prompt))


def check_wall_action(caption, spec):
    """Return (verified, reasons, evidence); uncertain evidence never passes."""
    if not wall_brace_required(spec):
        return None, [], {"required":False}
    desc=str(caption or "")
    evidence={
        "required":True,
        "wall_touch":bool(WALL_TOUCH.search(desc)),
        "both_hands":bool(BOTH_OBSERVED.search(desc)),
        "weight_on_feet":bool(SUPPORT.search(desc)),
        "forward_lean":bool(FORWARD.search(desc)),
        "ground_pose":bool(NEGATIVE_POSE.search(desc) or HANDS_GROUND.search(desc)),
        "uncertain":bool(UNCERTAIN.search(desc)),
    }
    if evidence["ground_pose"]:
        return False,["CG action mismatch: body or hands supported on ground instead of wall"],evidence
    missing=[name for name in ("wall_touch","both_hands","weight_on_feet","forward_lean")
             if not evidence[name]]
    if evidence["uncertain"] or missing:
        return False,["CG wall-contact action unverified: "+",".join(missing or ["uncertain"])],evidence
    return True,[],evidence
