"""Bounded independent evidence for explicitly declared visual objects.

Do NOT treat a successful landscape/person caption as evidence for props.
CLIP contrast is only an object/landmark indicator, never exact hand contact.
Unknown relation geometry stays unobservable (fail-closed).
"""
from __future__ import annotations

ENV_BASELINES={
 "outdoor_market_square":"an outdoor market square with many storefronts and stalls",
 "outdoor_street":"an outdoor street with ordinary houses and shops",
 "outdoor_courtyard":"an open courtyard surrounded by buildings",
 "outdoor_forest":"an outdoor forest clearing with trees",
 "indoor_room":"an indoor room with normal furniture",
 "indoor_tavern":"a furnished tavern with wooden tables",
 "underground_cave":"a rough dark underground cave interior",
}

def atomic_prompt_pair(assertion,environment):
    """Return an invariant QA-owned positive/counterfactual pair or None.

    Never take a counterfactual from the untrusted narrator: an easy negative
    would make a false positive appear certain. Relations require separate
    physical grounding rather than a whole-frame similarity score.
    """
    kind=str(assertion.get('kind') or '')
    obj=str(assertion.get('description') or '').strip()
    if len(obj)<3 or len(obj)>120 or any(x in obj for x in ('\n','\r','<','>')):
        return None
    if kind=='object':
        return ("a realistic scene with one adult person holding or using a clearly visible "+obj,
                "a realistic scene with a person holding an unrelated object in their hands")
    if kind=='landmark':
        baseline=ENV_BASELINES.get(environment)
        if not baseline:return None
        return ("a large architectural "+obj+" framing a person in the scene",
                baseline)
    return None

def atomic_decision(assertion,probability):
    """Three-state evidence, calibrated only on the current mini-fixture.

    A score is NOT an empirical probability of object existence. A positive
    CLIP contrast with a strong margin is a signal, not independent proof of
    acting/holding/contact. Explicit relations remain unobservable.
    """
    if assertion.get('kind')=='relation':return 'unobservable'
    if probability is None:return 'unobservable'
    try:score=float(probability)
    except (TypeError,ValueError):return 'unobservable'
    if not 0<=score<=1:return 'unobservable'
    if score>=.72:return 'verified'
    if score<=.40:return 'violated'
    return 'unobservable'

def required_atomic_items(spec):
    contract=(spec.get('visual_contract') or {}) if isinstance(spec,dict) else {}
    data=contract.get('required_visuals') or []
    return data if isinstance(data,list) else []


def atomic_report_matches_claims(requested,reported):
    """One independently checked verdict per requested atomic item, in order.

    An older or compromised vision response must never 'verify' all claims
    by returning a single unrelated positive. An unavailable/uncertain item
    stays rejected by the subsequent per-item verdict gate.
    """
    if not isinstance(requested,list) or not requested:
        return False
    if not isinstance(reported,list) or len(requested)!=len(reported):
        return False
    for i,(assertion,evidence) in enumerate(zip(requested,reported)):
        if not isinstance(assertion,dict) or not isinstance(evidence,dict):
            return False
        if evidence.get('index')!=i:
            return False
        if evidence.get('kind')!=assertion.get('kind'):
            return False
        if evidence.get('description')!=assertion.get('description'):
            return False
        if evidence.get('actor','')!=assertion.get('actor',''):
            return False
    return True
