"""Read-only per-shot scene-contract validation and human-readable conditioning.
Do not guess named actors or contact geometry from the model's prose.
"""
from math import isfinite

def _valid_contact_region(region):
    # Missing ROI is allowed; fabricated or malformed ROI is not.
    if region is None:
        return True
    return (isinstance(region, list) and len(region) == 4
            and all(type(v) in (int, float) and isfinite(v) for v in region)
            and region[0] >= 0 and region[1] >= 0
            and region[2] > 0 and region[3] > 0
            and region[0] + region[2] <= 1.00001
            and region[1] + region[3] <= 1.00001)

def scene_contract(spec):
    data=spec.get("visual_contract")
    if not isinstance(data,dict) or data.get("version")!=1:
        return None
    people=data.get("principals")
    if not isinstance(people,list) or len(people)>12:
        raise ValueError("Invalid scene contract principals")
    names=[p.get("name") for p in people if isinstance(p,dict)]
    if any(not isinstance(n,str) or not n.strip() for n in names) or len(names)!=len(people):
        raise ValueError("Malformed scene contract cast")
    if len(names)!=len(set(n.casefold() for n in names)):
        raise ValueError("Scene contract has duplicate principal names")
    if spec.get("composition")=="neural_story" and spec.get("kind")=="scene":
        authoritative=[str(p.get("name")) for p in spec.get("characters") or []]
        if names!=authoritative:
            raise ValueError("Scene contract diverges from authoritative cast")
    crowd=data.get("crowd") or {}
    if crowd.get("policy") not in ("none","ambient","crowd","unspecified"):
        raise ValueError("Invalid crowd policy")
    contacts=data.get("contacts") or []
    if not isinstance(contacts,list) or len(contacts)>12:
        raise ValueError("Invalid scene contacts")
    for contact in contacts:
        if not isinstance(contact, dict):
            raise ValueError("Malformed mandatory contact")
        target = contact.get("target")
        if (contact.get("actor") not in names
                or contact.get("kind") not in ("touch", "hold", "support", "lean_on")
                or not isinstance(target, str) or not target.strip()
                or not _valid_contact_region(contact.get("target_region"))):
            raise ValueError("Malformed mandatory contact: actor, action, target or ROI")
    return data

def crowd_condition(spec):
    contract=scene_contract(spec)
    if not contract:return "",""
    policy=contract["crowd"]["policy"]
    if policy=="none":
        return "Only the named principals, with no background people. ", "bystanders, crowded scene, "
    if policy=="ambient":
        return ("Exactly the named principal characters, plus optional small anonymous "
                "background pedestrians clearly behind them. No clones of principals. "), ""
    if policy=="crowd":
        return ("Exactly the named principal characters remain individually recognizable "
                "in front of the anonymous crowd. "), ""
    return "",""
