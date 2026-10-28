"""Stable conditioning guards for narrator-directed neural CG shots.

The storyteller owns the composition; these additions prevent repeated
diffusion artifacts (duplicate women, literal clock/camera props).
"""
def neural_scene_guards(spec,attempts=1,error="",subject=""):
    if spec.get("composition")!="neural_story":
        return "", "", ""
    cast=spec.get("characters") or []
    if not cast:
        return "", "", ""
    location=(spec.get("environment") or {}).get("id","")
    count=len(cast)
    if count==1:
        lead=(
            "SOLO FEMALE SUBJECT, solo, 1girl, one adult woman only, "
            "exactly one human body, exactly one head, one face, "
            "one continuous physical person, NOT two poses in the same frame. "
        )
        exclude=(
            "2girls, 3girls, two women, several women, additional woman, "
            "duplicate person, cloned face, twins, multiple people, double body, "
            "two versions of the same person, second figure, reflection of person, "
            "double exposure, inset portrait, photomontage, collage, "
        )
    else:
        lead=f"Exactly {count} separate established principal characters and no clones. "
        exclude="duplicate people, cloned faces, twins, second copy of subject, collage, "
    # Shot framing terms are not physical photography equipment.
    lead+="The described shot angle is the viewer's virtual viewpoint only. "
    exclude+=(
        "DSLR, photography camera, camera body, camera lens, tripod, "
        "film equipment, photographer, studio lights, wall-mounted clock, "
        "giant clock face, oversized clock, grey studio cyclorama, "
    )
    # A 'clock-like' shoulder mark had been hallucinated as a large wall clock.
    if any("clock" in str(x).lower() for x in [
            spec.get("world",""),subject,*(p.get("appearance","") for p in cast)]):
        lead+=(
            "The shoulder emblem is a SMALL FLAT SILVER TATTOO "
            "on the skin, with no separate associated prop. "
        )
    if location=="outdoor_market_square":
        lead+=(
            "SETTING MUST BE CLEARLY VISIBLE: open-air outdoor market square "
            "with storefronts, cobblestone street, daylight, market stalls "
            "and distant facades; not a featureless grey stone wall. "
        )
        exclude+="plain grey studio background, empty room, solid grey backdrop, "
    if attempts>1:
        # Retries should target the actual observed failures instead of
        # just reseeding the exact same contradictory conditioning.
        lead+=(
            "CORRECTION TO PRIOR FAILED ATTEMPT: keep the correct number of "
            "physical people and show the required outdoor environment. "
        )
    if "principal" in str(error).lower() or "competing=" in str(error).lower():
        lead+="REJECT DUPLICATION: no second body or copy of the subject. "
    return lead, exclude, "neural_scene_guards_v1"
