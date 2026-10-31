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
    elif len(people)==1:
        outfit=str(people[0].get("outfit","")).strip()
        if outfit and outfit.lower()!="default":
            positive.append(
                "CURRENT WARDROBE CONTRACT: match the CURRENT outfit exactly "
                "instead of the garments from the old character reference: "+
                outfit[:160]+"."
            )
    elif len(people)>1:
        # A mixed cast needs actor-bound positive wardrobe constraints.
        # Global garment negatives would incorrectly forbid another actor's
        # required clothes; face references must not supply old outfits.
        for actor in people:
            name=str(actor.get("name") or "").strip()[:80]
            outfit=str(actor.get("outfit") or "").strip()[:160]
            if not name or not outfit or outfit.lower()=="default":
                continue
            positive.append(
                "Actor "+name+" CURRENT outfit: "+outfit+". "
                "Keep this outfit on this actor only; canonical face "
                "references do not supply garments. Never transfer "
                "another actor's wardrobe."
            )
    # A per-actor declarative pose is advisory text unless it has its own
    # validated control reference. Never impose one actor's pose on the cast.
    for actor in people:
        descriptor=pose_contract(actor.get("pose"))
        if descriptor and descriptor["id"] not in ("stand_three_quarter",):
            positive.append("Actor "+str(actor.get("name",""))[:80]+
                " physical pose: "+descriptor["description"]+".")
    # The same resolved contract now governs pose selection, conditioning and QA.
    action_positive,action_negative=action_prompt_contract(spec,prompt)
    if action_positive:positive.insert(0,action_positive)
    if action_negative:negative.insert(0,action_negative)
    return " ".join(positive), ", ".join(negative)
