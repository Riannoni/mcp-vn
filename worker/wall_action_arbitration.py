"""Very narrow opt-in experiment: independent 2D corroboration + stronger VLM.

Never broad override. Production default OFF. Policy only corrects exactly one
known SmolVLM hallucination, after geometric and location checks already pass.
"""
from __future__ import annotations

SUPPORTED_REASONS={'CG action mismatch: ground-supported or kneeling pose',
 'CG wall contact unverified: wall_touch,weight_on_feet'}

def may_adjudicate(*,action_required,geometry,vision,qwen):
    if action_required is not True:return False
    if not isinstance(geometry,dict) or geometry.get('verified') is not True:return False
    contact=geometry.get('wall_contact_corroboration') or {}
    if contact.get('verdict')!='plausible':return False
    if not isinstance(qwen,dict) or qwen.get('verdict')!='wall_observed' or qwen.get('label')!='WALL':
        return False
    if not isinstance(vision,dict) or vision.get('status')!='failed':return False
    reasons=vision.get('reasons') or []
    if not isinstance(reasons,list) or len(reasons)!=1 or reasons[0] not in SUPPORTED_REASONS:
        return False
    if vision.get('scene_count_verified') is not True:return False
    if vision.get('scene_location_verified') is not True:return False
    evidence=vision.get('scene_action_evidence') or {}
    if evidence.get('required') is not True or evidence.get('forward_lean') is not True or evidence.get('both_hands') is not True:
        return False
    # In this single known error, Smol said 'ground_pose=true' but Qwen+
    # DWPose+independent detected wall disagree. Other action mismatches do
    # not qualify. Still requires entire worker.assess postchecks afterwards.
    return True
