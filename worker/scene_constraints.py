"""Structured visual constraints derived from the CURRENT scene, not prior sprites.

This is deliberately small: the narrator remains the director of the camera,
but the wardrobe/physical action recorded in the game state must not be lost
inside a long positive prompt or the canonical face reference.
"""
from wardrobe_contract import wants_unclothed
from scene_action_contract import action_prompt_contract
from pose_contracts import pose_contract

def scene_constraints(spec, prompt):
    if spec.get("composition") != "neural_story":
        return "", ""
    people=spec.get("characters") or []
    if not people:
        return "", ""
    positive=[]
    negative=[]
    # Global wardrobe exclusion is only safe when all visible actors share
    # that clothing state. Mixed outfits must NOT be excluded globally.
    if all(wants_unclothed(a.get("outfit","")) for a in people):
        positive.append(
            "CURRENT WARDROBE CONTRACT: all visible characters wear no garments. "
            "Canonical reference images provide facial identity ONLY; NEVER copy "
            "their prior costume, neckline or accessories onto the current body. "
            "Any discarded clothing is separate from the person."
        )
        negative.append(
            "worn clothing, clothes on body, green cloak, shawl, scarf, "
            "shirt, blouse, top, sleeves, jacket, vest, pants, trousers, "
            "skirt, dress, fabric wrapped on body, collar, boots, underwear"
        )
    else:
        # Actor-specific garments are authoritative even in a mixed cast.
        # A global negative garment list would erase clothing from actors
        # who are supposed to wear it; scope requirements by actor instead.
        for actor in people:
            outfit=str(actor.get("outfit","")).strip()
            if not outfit or outfit.lower()=="default":
                continue
            name=str(actor.get("name","")).strip()[:80]
            if wants_unclothed(outfit):
                positive.append(
                    "CURRENT WARDROBE CONTRACT for "+name+": no garments worn "
                    "on this person's body; any discarded clothing is separate. "
                    "Do not copy clothing from the identity reference."
                )
            else:
                positive.append(
                    "CURRENT WARDROBE CONTRACT for "+name+": "+outfit[:160]+
                    ". Match this actor's CURRENT garments instead of the "
                    "garments from the old character reference."
                )
    # A per-actor declarative pose is advisory text unless it has its own
    # validated control reference. Never impose one actor's pose on the cast.
    for actor in people:
        descriptor=pose_contract(actor.get("pose"))
        if descriptor and descriptor["id"] not in ("stand_three_quarter",):
            positive.append("Actor "+str(actor.get("name",""))[:80]+
                " physical pose: "+descriptor["description"]+".")
    # Typed required objects get top priority independently of short narrator
    # prompts. This is a generation instruction, NOT a QA acceptance verdict.
    for item in ((spec.get("visual_contract") or {}).get("required_visuals") or [])[:8]:
        kind=item.get("kind")
        description=str(item.get("description") or "")[:120]
        actor=str(item.get("actor") or "")[:80]
        action=str(item.get("action") or "")[:80]
        if kind in ("object","landmark","relation") and description:
            positive.insert(0,"MANDATORY VISUAL "+kind.upper()+": "+description+
                ("; actor "+actor if actor else "")+
                ("; action "+action if action else "")+".")
    # The same resolved contract now governs pose selection, conditioning and QA.
    action_positive,action_negative=action_prompt_contract(spec,prompt)
    if action_positive:positive.insert(0,action_positive)
    if action_negative:negative.insert(0,action_negative)
    return " ".join(positive), ", ".join(negative)
