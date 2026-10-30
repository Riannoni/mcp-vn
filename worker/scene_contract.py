"""Read-only per-shot scene-contract validation and human-readable conditioning.
Do not guess named actors or contact geometry from the model's prose.
"""
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
        if not isinstance(contact,dict) or contact.get("actor") not in names or (
           contact.get("kind") not in ("touch","hold","support","lean_on")):
            raise ValueError("Contact actor/action is not anchored in cast")
    visuals=data.get("required_visuals") or []
    if not isinstance(visuals,list) or len(visuals)>8:
        raise ValueError("Invalid atomic scene requirements")
    for item in visuals:
        if not isinstance(item,dict) or item.get("kind") not in ("object","landmark","relation"):
            raise ValueError("Invalid atomic scene kind")
        if not isinstance(item.get("description"),str) or not 3<=len(item["description"])<=120:
            raise ValueError("Invalid atomic description")
        if item.get("actor") and item["actor"] not in names:
            raise ValueError("Unknown actor in atomic requirement")
        if item["kind"]=="relation" and not (item.get("actor") and item.get("action")):
            raise ValueError("Relation requires actor and action")
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
