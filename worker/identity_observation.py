"""Explicit view intent is not proof of facial identity in a rendered bitmap."""
import re
REAR=re.compile(
    r"\b(?:rear view|back view|from behind|facing away|back to (?:the )?camera|"
    r"head turned away|face (?:hidden|occluded|not visible))\b|"
    r"со спины|спиной к камере|лицо не видно|вид сзади",re.I)
def face_observability(spec):
    variant=spec.get("variant") or {}
    pose=str(variant.get("pose") or "")
    if REAR.search(pose):
        return {"verdict":"unobservable","reason":"requested_rear_or_occluded_face"}
    return {"verdict":"potentially_visible","reason":"pose_does_not_preclude_face"}


def face_similarity_decision(spec,similarity,caption):
    """Only skip a facial comparison when BOTH plan and image description
    indicate an occluded/rear face. The image report remains unobservable.
    A requested rear pose alone cannot bypass an observed frontal mismatch.
    """
    intent=face_observability(spec).get("verdict")
    actual=bool(REAR.search(str(caption or "")))
    if intent=="unobservable" and actual:
        return {"verdict":"unobservable","reason":"rear_pose_corrobated"}
    if similarity is None:
        return {"verdict":"unobservable","reason":"no_face_reference"}
    if similarity<.80:
        return {"verdict":"violated","reason":"face_similarity_low"}
    if similarity<.86:
        return {"verdict":"unobservable","reason":"face_similarity_borderline"}
    return {"verdict":"verified","reason":"face_similarity_sufficient"}
