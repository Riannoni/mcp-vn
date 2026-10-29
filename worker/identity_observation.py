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
