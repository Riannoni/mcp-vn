"""Advisory image/text contrast labels for a freeform visual-novel scene.

Text-image scores are not proof of exact pose, action or wardrobe correctness.
There is no content-category filtering here.
"""

def action_contrast_captions(spec):
    state=(spec or {}).get("local_visual_state") or {}
    characters=state.get("characters") or []
    activity=str(state.get("activity") or "").strip()
    if not characters or not activity:
        return None
    cast=[]
    for actor in characters[:3]:
        name=str(actor.get("name") or "character")[:28]
        pose=str(actor.get("pose") or "").strip()[:65]
        action=str(actor.get("action") or "").strip()[:90]
        if pose or action:
            cast.append(f"{name} {pose} {action}".strip())
    if not cast:
        return None
    target=("A cinematic scene of "+activity[:115]+". "+"; ".join(cast)[:190])[:295]
    count=len(characters)
    neutral=(f"A conventional still portrait of exactly {count} adults "
             "standing straight, motionless, looking at the camera, no interaction.")
    return target,neutral
