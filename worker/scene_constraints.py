"""Structured visual constraints derived from the CURRENT scene, not prior sprites.

This is deliberately small: the narrator remains the director of the camera,
but the wardrobe/physical action recorded in the game state must not be lost
inside a long positive prompt or the canonical face reference.
"""
from wardrobe_contract import wants_unclothed

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
    # Put structured physical contact ahead of environment decoration.
    # The old output repeatedly placed a person reclining on street paving
    # instead of bracing against the requested wall.
    subj=str(prompt or "").lower()
    poses=" ".join(str(p.get("pose","")) for p in people).lower()
    if len(people)==1 and (
        ("wall" in subj or "masonry" in subj or "стен" in subj) and
        ("palm" in subj or "hand" in subj or "brac" in subj or
         "lean" in subj or "lean" in poses)
    ):
        positive.append(
            "PHYSICAL ACTION: hands touch a VERTICAL stone wall, torso "
            "leans forward from the waist, feet and legs remain on the ground "
            "supporting the body. The wall is directly beside the character, "
            "with the market in the background, not a freestanding portrait."
        )
        negative.append(
            "lying on ground, lying on stomach, reclining on paving stones, "
            "prone pose, crawling, elbows resting on cobblestone ground, "
            "standing alone in middle of street, hands on ground"
        )
    return " ".join(positive), ", ".join(negative)
