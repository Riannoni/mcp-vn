"""Validated, view-explicit two-hand prop blocking for *draft* pose guides.

The storyteller or editor MUST supply spatial targets. Never infer coordinates
from the last frame, generic prompt, or another game's actor. This is only
preflight geometry, not proof that generation fulfills the prop interaction.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib,json,math

class BlockingError(ValueError):pass

def _point(value,name):
    if not isinstance(value,dict):raise BlockingError(name+'_missing')
    try:x,y=value['x'],value['y']
    except KeyError:raise BlockingError(name+'_coordinates_missing') from None
    if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or not 0<=v<=1 for v in (x,y)):
        raise BlockingError(name+'_coordinates_invalid')
    return float(x),float(y)

def validate_bimanual_prop(plan,known_principals):
    if not isinstance(plan,dict) or plan.get('version')!=1:
        raise BlockingError('unsupported_interaction_version')
    actor=plan.get('actor_id');obj=plan.get('object_id')
    if not isinstance(actor,str) or actor not in known_principals or not actor:
        raise BlockingError('unknown_principal')
    if not isinstance(obj,str) or not obj or len(obj)>70:
        raise BlockingError('object_id_missing')
    if plan.get('view')!='front':
        raise BlockingError('view_not_yet_supported')
    region=plan.get('object_region')
    if not isinstance(region,dict):raise BlockingError('object_region_missing')
    x0,y0=_point({'x':region.get('x0'),'y':region.get('y0')},'object_min')
    x1,y1=_point({'x':region.get('x1'),'y':region.get('y1')},'object_max')
    if not (.10<=x1-x0<=.5 and .09<=y1-y0<=.42 and .15<y0<.75):
        raise BlockingError('object_bbox_unrealistic')
    physical_right=_point(plan.get('right_hand'),'right_hand')
    physical_left=_point(plan.get('left_hand'),'left_hand')
    if physical_right[0]>=physical_left[0]:
        raise BlockingError('front_view_hands_misordered')
    if physical_left[0]-physical_right[0]<.10:
        raise BlockingError('hands_not_separated')
    edge=max(.026,(x1-x0)*.19)
    if not(abs(physical_right[0]-x0)<=edge and abs(physical_left[0]-x1)<=edge):
        raise BlockingError('hands_not_near_object_edges')
    if not all(y0-.025<=pt[1]<=y1+.025 for pt in (physical_right,physical_left)):
        raise BlockingError('hands_vertically_separated_from_object')
    normalized={
        'version':1,'actor_id':actor,'object_id':obj,'view':'front',
        'object_region':{'x0':x0,'y0':y0,'x1':x1,'y1':y1},
        'right_hand':{'x':physical_right[0],'y':physical_right[1]},
        'left_hand':{'x':physical_left[0],'y':physical_left[1]},
        'status':'draft_requires_gpu_and_visual_validation'}
    return normalized

def draft_pose_from_front_template(template,plan):
    """Return a non-approved skeleton with wrists fixed to explicit targets."""
    if plan.get('status')!='draft_requires_gpu_and_visual_validation':
        raise BlockingError('plan_must_be_validated_first')
    p=deepcopy(template)
    people=p.get('people') or []
    if len(people)!=1:raise BlockingError('single_principal_template_required')
    arr=people[0].get('pose_keypoints_2d') or []
    w,h=p.get('canvas_width'),p.get('canvas_height')
    if not isinstance(w,int) or not isinstance(h,int) or len(arr)<54:
        raise BlockingError('invalid_skeleton_template')
    def point(i):return (float(arr[3*i])/w,float(arr[3*i+1])/h)
    def put(i,xy):arr[3*i:3*i+3]=[round(xy[0]*w),round(xy[1]*h),1.0]
    for wrist,elbow,shoulder,name in ((4,3,2,'right_hand'),(7,6,5,'left_hand')):
        target=(plan[name]['x'],plan[name]['y']);start=point(shoulder)
        # Elbow lies between shoulder and target wrist, slightly outward.
        mid=(start[0]+(target[0]-start[0])*.52,start[1]+(target[1]-start[1])*.56)
        put(elbow,mid);put(wrist,target)
    p['name']='present_bimanual_prop_front'
    p['label']='Draft two-handed object presentation — human and GPU approval required'
    p['camera']='front';p['status']='draft_requires_gpu_validation'
    p['interaction_contract_hash']=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    return p
