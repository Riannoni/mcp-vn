"""Evidence rules for scene correspondence, separate from model prompting.

A generated asset is technically valid when it is a PNG/MP4. It is *scene
grounded* only when independent CLIP evidence corroborates the requested
location and principal-person count. A one-word SmolVLM answer such as
"Two." is not evidence by itself. No content-category filters are here.
"""

def principal_count_evidence(expected_count, scores):
    """Return (verified, reasons, confidence) for visible principals."""
    n=int(expected_count or 0)
    if n <= 0:
        return False, ["Scene has no declared principal characters"], 0.0
    solo=sum(float(scores.get(k,0)) for k in ("solo_portrait","solo_person","solo_woman"))
    pair=sum(float(scores.get(k,0)) for k in ("pair_people","pair_interaction","pair_mixed"))
    group=sum(float(scores.get(k,0)) for k in ("group_three","group_many"))
    empty=float(scores.get("no_people",0))
    if n == 1:
        positive=solo
        competitors=pair+group+empty
        verified=(positive>=0.12 and positive>pair*1.0 and
                  positive>group*1.0 and positive>empty*1.0)
    elif n == 2:
        positive=pair
        competitors=solo+group+empty
        verified=(positive>=0.31 and positive>solo*1.25 and
                  positive>group*1.10 and positive>empty*1.5)
    else:
        positive=group
        competitors=solo+pair+empty
        verified=(positive>=0.30 and positive>solo*1.2 and
                  positive>pair*1.1 and positive>empty*1.5)
    if verified:
        return True, [], round(positive,4)
    if n == 2:
        reason=("Two distinct principal figures cannot be independently verified: "
                f"CLIP two={pair:.3f}, one={solo:.3f}, group={group:.3f}")
    else:
        reason=(f"Expected {n} principal figures cannot be verified: "
                f"matched={positive:.3f}, competing={competitors:.3f}")
    return False,[reason],round(positive,4)


def scene_location_evidence(expected, scores):
    """Return (verified, reasons, score). Distinguish forest versus market."""
    categories=(
      "outdoor_market_square","outdoor_street","outdoor_forest",
      "outdoor_courtyard","indoor_room","indoor_tavern","underground_cave"
    )
    expected=str(expected or "")
    if expected not in categories:
        return False,[],0.0  # unknown setting: not eligible for reference reuse
    val=float(scores.get(expected,0))
    forest=float(scores.get("outdoor_forest",0))
    market=float(scores.get("outdoor_market_square",0))
    street=float(scores.get("outdoor_street",0))
    courtyard=float(scores.get("outdoor_courtyard",0))
    urban=market+street+courtyard
    reasons=[]
    if expected in ("outdoor_market_square","outdoor_street","outdoor_courtyard"):
        if forest>=.27 and forest>urban*1.20:
            reasons.append(
              f"Requested {expected}, but CLIP strongly identifies forest "
              f"(forest={forest:.3f}, urban={urban:.3f})")
    elif expected=="outdoor_forest":
        if urban>.50 and forest<.13:
            reasons.append(
              f"Requested forest, but CLIP strongly identifies urban scene "
              f"(forest={forest:.3f}, urban={urban:.3f})")
    return not reasons,reasons,round(val,4)
