"""Evidence rules for scene correspondence, separate from model prompting.

A generated asset is technically valid when it is a PNG/MP4. It is *scene
grounded* only when independent CLIP evidence corroborates the requested
location and principal-person count. A one-word SmolVLM answer such as
"Two." is not evidence by itself. No content-category filters are here.
"""

def principal_count_evidence(expected_count, scores, crowd_policy="none"):
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
        verified=(positive>=0.29 and positive>pair*1.15 and
                  positive>group*1.08 and positive>empty*1.5)
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
    # A permissive crowd permits MORE people than declared principals, never
    # fewer. A global CLIP count cannot certify named identity/actor identity.
    if crowd_policy in ("ambient","crowd") and n in (1,2):
        group_compatible=group>=.25 and group>empty*1.5 and group>solo*.85
        pair_compatible=pair>=.29 and pair>empty*1.5
        if n==1 and (positive>=.29 or pair_compatible or group_compatible):
            return True,[],round(max(positive,pair,group),4)
        if n==2 and (pair_compatible or group_compatible) and                 max(pair,group)>solo*1.08:
            return True,[],round(max(pair,group),4)
        return False,[f"At least {n} people not independently corroborated "
           f"with extras allowed (solo={solo:.3f}, pair={pair:.3f}, group={group:.3f})"],round(max(pair,group),4)
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
    indoor=sum(float(scores.get(k,0)) for k in ("indoor_room","indoor_tavern","underground_cave"))
    outdoor=sum(float(scores.get(k,0)) for k in ("outdoor_market_square",
                        "outdoor_street","outdoor_forest","outdoor_courtyard"))
    if expected.startswith("outdoor_") and indoor>=.55 and indoor>outdoor*1.35:
        return False,[f"Requested outdoor location {expected}, but indoor evidence dominates "
                      f"(indoor={indoor:.3f}, outdoor={outdoor:.3f})"],round(val,4)
    if (expected.startswith("indoor_") or expected=="underground_cave") and (
            outdoor>=.65 and outdoor>indoor*1.5):
        return False,[f"Requested indoor location {expected}, but outdoor evidence dominates"],round(val,4)
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
    # A noncontradictory image isn't automatically positive evidence.
    # Preserve as unobservable when another setting outranks the requested
    # scene by even a small margin, without issuing an uncalibrated rejection.
    top=max((float(scores.get(k,0)) for k in categories if k!=expected),default=0)
    verified=(not reasons and val>=.20 and val>=top*.92)
    return verified,reasons,round(val,4)
