"""Structured visual constraints derived from the CURRENT scene, not prior sprites.

This is deliberately small: the narrator remains the director of the camera,
but the wardrobe/physical action recorded in the game state must not be lost
inside a long positive prompt or the canonical face reference.
"""
from wardrobe_contract import wants_unclothed
from scene_action_contract import action_prompt_contract

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
    # The same resolved contract now governs pose selection, conditioning and QA.
    action_positive,action_negative=action_prompt_contract(spec,prompt)
    if action_positive:positive.insert(0,action_positive)
    if action_negative:negative.insert(0,action_negative)
    return " ".join(positive), ", ".join(negative)
