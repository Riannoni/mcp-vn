"""Shared, deterministic visual-action intent for story CGs.

Single source of truth: pose selection, generation conditioning and QA must
interpret the SAME scene. Conservative recognition is preferable to inventing
an action or silently rendering one without its required pose guide.

Extend this module with new *explicit* action categories as approved
reference poses become available. Never substitute a vaguely similar guide.
"""
from __future__ import annotations
import re

WALL=re.compile(r"\b(?:wall|masonry|brickwork|stonework|stone\s+surface|"
                r"stone\s+face)\b|стен[а-я]*",re.I)
LEAN=re.compile(r"\b(?:lean(?:s|ing)?|bent|bend(?:s|ing)?|"
                r"brac(?:es|ed|ing)?|hing(?:e|es|ed|ing))\b|"
                r"наклон[а-я]*|упира[а-я]*",re.I)
HANDS=re.compile(r"\b(?:palms?|hands?)\b|ладон[а-я]*|рук[а-я]*",re.I)
PLANTED=re.compile(r"\b(?:plant(?:ed|ing)?|press(?:ed|ing)?|"
                   r"brac(?:ed|ing)?|rest(?:ing)?|"
                   r"plac(?:ed|ing)?|touch(?:ed|ing)?|"
                   r"against|onto|on\s+(?:it|the\s+(?:stone|wall)))\b|"
                   r"упира[а-я]*|клад[а-я]*|лож[а-я]*",re.I)
GROUND_CONTACT=re.compile(
    r"\b(?:palms?|hands?|elbows?)\b.{0,45}"
    r"\b(?:on|against|touch(?:ing)?|press(?:ed|ing)?|plant(?:ed|ing)?)\b"
    r".{0,28}\b(?:ground|floor|pavement|paving|street|"
    r"cobblestones|road)\b",re.I)
REAR=re.compile(r"\b(?:from behind|rear[\s-]+three[\s-]+quarter"
                r"(?:[\s-]+view|[\s-]+angle|[\s-]+medium[\s-]+shot)?|"
                r"rear[\s-]+(?:view|angle)|three[\s-]+quarter[\s-]+rear|"
                r"back[\s-]+view|view from the back|"
                r"camera behind the character)\b|"
                r"со\s+спины|сзади",re.I)
SIDE=re.compile(r"\b(?:side[\s-]+view|side[\s-]+angle|"
                r"side[\s-]+profile|from the side|profile view)\b|"
                r"сбоку|профил[ья]",re.I)
HIP=re.compile(
    r"\b(?:hips?|waist|hip[\s-]?hinge|torso\s+horizontal|"
    r"(?:legs?|knees?)\s+(?:remain\s+)?straight|"
    r"(?:back|spine)\s+(?:slightly\s+)?arched|"
    r"legs?\s+apart|head\s+lowered)\b|"
    r"поясниц[а-я]*|тазобедрен[а-я]*|согнувш[а-я]*",re.I)

# Deliberate negative evidence: a person may lean near a wall while
# bracing with hands on the ground. Do not treat wall proximity as contact.
# A one-hand action must never be rewritten as an approved TWO-hand guide.
# Keep narrator instructions authoritative; there is no approved single-hand
# ControlNet reference in this library yet.
ONE_HAND=re.compile(
    r"\b(?:one|single|left|right)\s+(?:hand|palm)\b|"
    r"\b(?:his|her|their)\s+(?:left|right)\s+(?:hand|palm)\b|"
    r"одн(?:ой|у|а)\s+(?:рук|ладон)|"
    r"(?:лев|прав)[а-я]*\s+(?:рук|ладон)",re.I)

NO_WALL_ACTION=re.compile(
    r"\b(?:hands?|palms?)\b.{0,35}"
    r"\b(?:by (?:her|his|their) sides?|behind (?:her|his|their) back|"
    r"on (?:the )?(?:ground|pavement|floor|street|road))\b",re.I)
BAD_POSE=re.compile(
    r"\b(?:lying|laying|reclining|crawling|kneeling|"
    r"on all fours|hands and knees|sitting|crouching|squatting|"
    r"on (?:the )?(?:ground|floor))\b",re.I)
WALL_TOUCH=re.compile(
    r"\b(?:palms?|hands?)\b.{0,65}"
    r"\b(?:on|onto|touch(?:ing)?|press(?:ed|ing)?|against|"
    r"brac(?:ed|ing)?|rest(?:ing)?|plant(?:ed|ing)?|plac(?:ed|ing)?)\b"
    r".{0,60}\b(?:wall|masonry|stonework|brickwork)\b"
    r"|\b(?:wall|masonry|stonework|brickwork)\b.{0,55}"
    r"\b(?:touch(?:ing)?|press(?:ed|ing)?|brac(?:ed|ing)?|against)\b"
    r".{0,35}\b(?:hands?|palms?)\b",re.I)
BOTH=re.compile(r"\b(?:both|two)\b.{0,38}\b(?:hands?|palms?)\b"
                r"|\b(?:hands?|palms?)\b.{0,32}\b(?:both|two)\b",re.I)
SUPPORT=re.compile(r"\b(?:stands?|standing|feet|foot|legs?\s+straight|"
                   r"on (?:her|his|their|both) feet)\b",re.I)
FORWARD=re.compile(r"\b(?:lean(?:s|ing)?|bend(?:s|ing)?|bent|"
                   r"hing(?:e|es|ed|ing))\b.{0,60}"
                   r"\b(?:forward|toward|towards|wall|waist|hip)\b"
                   r"|\b(?:torso|body)\b.{0,35}"
                   r"\b(?:forward|bent|leaning|horizontal|hinged)\b",re.I)
UNCERTAIN=re.compile(r"\b(?:unclear|can't tell|cannot tell|"
                     r"not visible|hidden|cannot see|not possible to see)\b",re.I)


def resolve_scene_action(spec, prompt=None):
    """Return a typed visual-action contract, not a guessed pose guide.

    Non-neural and multi-actor compositions are left alone: mixing separate
    actor poses requires explicit person/region association not available here.
    """
    spec=spec or {}
    actors=spec.get("characters") or []
    text=str(prompt if prompt is not None else spec.get("prompt") or "")
    if spec.get("composition")!="neural_story" or len(actors)!=1:
        return {"required":False,"action":None,"camera":None,
                "reason":"unsupported_composition"}
    pose=str(actors[0].get("pose") or "")
    t=text+" "+pose
    if not (WALL.search(t) and LEAN.search(t) and HANDS.search(t)):
        return {"required":False,"action":None,"camera":None,
                "reason":"no_explicit_wall_brace"}
    if ONE_HAND.search(t):
        return {"required":False,"action":None,"camera":None,
                "reason":"single_hand_action_has_no_approved_two_hand_guide"}
    if GROUND_CONTACT.search(t) or NO_WALL_ACTION.search(t):
        return {"required":False,"action":None,"camera":None,
                "reason":"hands_not_on_wall"}
    # When the narrator says "palms planted" immediately after "against
    # the wall" the recipient of "planted" is the wall, even without "both".
    if not (PLANTED.search(t) or
            re.search(r"\b(?:palms?|hands?)\b.{0,35}\bwall\b",t,re.I)):
        return {"required":False,"action":None,"camera":None,
                "reason":"contact_not_described"}
    camera_text=str(spec.get("camera") or "")
    scene=t+" "+camera_text
    rear=bool(REAR.search(scene))
    side=bool(SIDE.search(scene))
    camera="rear" if rear and not side else "side" if side and not rear else None
    hinge=bool(HIP.search(t) or
               re.search(r"\blean(?:s|ing)?\s+forward\s+against\s+(?:the\s+)?wall\b",pose,re.I))
    action="palms_on_wall_hip_hinge" if hinge else "palms_on_wall"
    return {"required":True,"action":action,"camera":camera,
            "reason":"exact_action" if camera else "camera_missing_or_ambiguous",
            "hands_contact":"vertical_wall","body_support":"standing_feet",
            "body_pose":"forward_hip_hinge" if hinge else "standing_forward_lean"}


def scene_action_key(prompt,characters=None):
    spec={"composition":"neural_story",
          "characters":characters or [{"name":"single adult"}],
          "prompt":str(prompt or "")}
    contract=resolve_scene_action(spec)
    return contract["action"],contract["camera"]


def wall_brace_required(spec):
    return resolve_scene_action(spec)["required"]


def action_prompt_contract(spec,prompt=None):
    action=resolve_scene_action(spec,prompt)
    if not action["required"]:
        return "",""
    pos=("PHYSICAL ACTION CONTRACT: exactly one adult stands upright on their "
         "feet beside a VERTICAL wall. Both palms press flat against the "
         "vertical stone masonry, not the pavement. Body weight is supported "
         "by feet and hands on the wall; knees do not touch the ground. "
         "Upper body leans forward toward the wall. "
         "Both arms clearly reach the wall, the wall is visible in contact.")
    if action["body_pose"]=="forward_hip_hinge":
        pos+=" Hinge forward at the hips, back slightly arched, legs extended."
    if action["camera"]=="rear":
        pos+=" Rear or rear three-quarter view; wall is directly in front of subject."
    elif action["camera"]=="side":
        pos+=" Side view clearly showing the hands-to-wall physical contact."
    neg=("kneeling, sitting, crouching, squatting, crawling, on all fours, "
         "lying on paving, hands on cobblestones, palms on ground, elbows on "
         "pavement, ground-supported pose, hands nowhere near wall, "
         "standing in center of street without contact, unrelated pin-up pose")
    return pos,neg


def check_wall_action(caption,spec):
    if not wall_brace_required(spec):
        return None,[],{"required":False}
    desc=str(caption or "")
    evidence={
        "required":True,
        "wall_touch":bool(WALL_TOUCH.search(desc)),
        "both_hands":bool(BOTH.search(desc)),
        "weight_on_feet":bool(SUPPORT.search(desc)),
        "forward_lean":bool(FORWARD.search(desc)),
        "ground_pose":bool(BAD_POSE.search(desc) or GROUND_CONTACT.search(desc)),
        "uncertain":bool(UNCERTAIN.search(desc)),
    }
    if evidence["ground_pose"]:
        return False,["CG action mismatch: ground-supported or kneeling pose"],evidence
    missing=[k for k in ("wall_touch","both_hands","weight_on_feet","forward_lean")
             if not evidence[k]]
    if missing or evidence["uncertain"]:
        return False,["CG wall contact unverified: "+",".join(missing or ["uncertain"])],evidence
    return True,[],evidence
