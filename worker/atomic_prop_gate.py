"""Independent typed prop/contact evidence aggregation. SHADOW ONLY.

This module does not produce 'scene passed'. Its positive conclusion is
'plausible_pending_scene_qa', which cannot bypass wardrobe, identity, location
or full visual contract. Every missing mandatory observation rejects publication.
"""
from __future__ import annotations
from math import isfinite
from prop_scale_evidence import assess as projected_scale

_ALLOWED_OBJECT=("verified","violated","unobservable")
_ALLOWED_CONTACT=("both_touch","one_touch","none","unobservable")

def evaluate(required, observations):
    """Return a fail-closed gate report without contacting an image model.

    required: typed actor_id, target_id, contact_kind, max_width_to_shoulders,
              front/same_depth. observations: actor/object provenance plus
              already attributed DWPose/Florence bbox and atomic contact QA.
    """
    result={"status":"rejected","reasons":[],"evidence":{},
            "can_publish":False,"note":"independent local prop gate, never full scene QA"}
    if not isinstance(required,dict) or not isinstance(observations,dict):
        result["reasons"].append("typed_prop_contract_or_observations_missing")
        return result
    actor=required.get("actor_id")
    target=required.get("target_id")
    kind=required.get("contact_kind")
    bound=required.get("max_width_to_shoulders")
    if (not isinstance(actor,str) or not actor.strip() or
            not isinstance(target,str) or not target.strip() or
            kind not in ("hold_both_hands","touch_both_hands") or
            isinstance(bound,bool) or not isinstance(bound,(int,float)) or
            not isfinite(bound) or not .15<=bound<=2.0):
        result["reasons"].append("typed_prop_contract_invalid")
        return result
    if (observations.get("actor_id")!=actor or
            observations.get("target_id")!=target):
        result["reasons"].append("object_or_actor_attribution_mismatch")
        return result
    semantics=observations.get("object_match","unobservable")
    if semantics not in _ALLOWED_OBJECT:
        semantics="unobservable"
    result["evidence"]["object"]={"verdict":semantics,
         "method":observations.get("object_method","unobservable")}
    if semantics=="violated":
        result["reasons"].append("mandatory_required_object_mismatch")
    elif semantics!="verified":
        result["reasons"].append("mandatory_required_object_unobservable")
    # Do not interpret a yes/no VLM answer alone as object presence if its
    # source/provenance is missing or unknown.
    if observations.get("object_method") not in ("florence_grounding", "human_labeled"):
        result["reasons"].append("object_grounding_provenance_missing")
    scale=projected_scale(observations.get("pose_frame"),
        observations.get("principal_index"), observations.get("object_boxes"),
        observations.get("detector_size"),max_object_to_shoulder_ratio=bound,
        view=required.get("view"),same_depth=required.get("same_depth"))
    result["evidence"]["projected_size"]=scale
    if scale["verdict"]=="violated":
        result["reasons"].append("required_object_exceeds_typed_projected_size")
    elif scale["verdict"]!="plausible":
        result["reasons"].append("mandatory_object_scale_unobservable")
    # DWPose proximity alone is explicitly insufficient contact evidence.
    touch=observations.get("contact_verdict","unobservable")
    if touch not in _ALLOWED_CONTACT:touch="unobservable"
    result["evidence"]["contact"]={"verdict":touch,
       "method":observations.get("contact_method","unobservable")}
    if touch in ("one_touch","none"):
        result["reasons"].append("mandatory_two_hand_contact_violated")
    elif touch!="both_touch":
        result["reasons"].append("mandatory_two_hand_contact_unobservable")
    if touch=="both_touch" and observations.get("contact_method") not in (
            "independent_atomic_vlm", "human_labeled"):
        result["reasons"].append("physical_contact_provenance_missing")
    if not result["reasons"]:
        result["status"]="plausible_pending_scene_qa"
    return result
