"""Reusable guarded native Klein inpaint graph for isolated staged CGs.

Requires explicit original source pixels, edit permission PNG and protected
regions. No story-specific assumptions and no publishing. Accepting any image
still requires full Scene Contract QA and scene-state version checks.
"""
from __future__ import annotations
from copy import deepcopy
from io import BytesIO
from pathlib import PurePath
from math import isfinite

class StagedSceneError(ValueError):pass


def _name(name):
    if not isinstance(name,str) or not name or len(name)>190 or '/' in name or '\\' in name or '..' in name:
        raise StagedSceneError('unsafe_comfy_image_name')
    if not name.lower().endswith('.png'):
        raise StagedSceneError('upload_must_be_png')
    return name


def verify_mask(inverse_alpha_png, source_size, protected_regions, *,
                source_pose=None, principal_index=None, actor_change_policy=None):
    """Preflight mask: Comfy LoadImage mask comes from inverse PNG alpha."""
    from PIL import Image,ImageOps
    try:
        with Image.open(BytesIO(inverse_alpha_png)) as m:
            if m.format!='PNG':raise StagedSceneError('mask_must_be_png')
            if m.mode!='RGBA':raise StagedSceneError('mask_must_have_alpha')
            edit=ImageOps.invert(m.getchannel('A'))
    except (OSError,ValueError,TypeError) as e:
        if isinstance(e,StagedSceneError):raise
        raise StagedSceneError('mask_png_unreadable') from e
    if edit.size!=tuple(source_size):raise StagedSceneError('mask_canvas_mismatch')
    n=edit.width*edit.height
    hist=edit.histogram()
    fraction=sum(i*v for i,v in enumerate(hist))/(255*n)
    if not .01<=fraction<=.70:raise StagedSceneError('edit_area_out_of_bounds')
    if not isinstance(protected_regions,(tuple,list)) or not protected_regions:
        raise StagedSceneError('protected_regions_required')
    for region in protected_regions:
        if not isinstance(region,(tuple,list)) or len(region)!=4:
            raise StagedSceneError('protected_rect_invalid')
        try:x0,y0,x1,y1=region
        except (ValueError,TypeError):raise StagedSceneError('protected_rect_invalid')
        if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v) for v in region):
            raise StagedSceneError('protected_rect_invalid')
        if not (0<=x0<x1<=1 and 0<=y0<y1<=1):
            raise StagedSceneError('protected_rect_invalid')
        w,h=edit.size
        crop=edit.crop((int(x0*w),int(y0*h),int(x1*w),int(y1*h)))
        if crop.getextrema()[1]>0:raise StagedSceneError('protected_pixels_would_change')
    anatomy=None
    if actor_change_policy is not None:
        action=(actor_change_policy.get("action") if isinstance(actor_change_policy,dict) else None)
        if action not in ("stationary_upper_body_prop", "stationary_upper_body_prop_strict"):
            raise StagedSceneError("unsupported_actor_change_policy")
        if source_pose is None or principal_index is None:
            raise StagedSceneError("actor_policy_requires_attributed_source_pose")
        from actor_edit_policy import ActorEditPolicyError, check_stationary_upper_body_mask
        try:
            anatomy=check_stationary_upper_body_mask(
                edit, source_pose, principal_index,
                keypoint_format=actor_change_policy.get("keypoint_format", "openpose18"))
        except ActorEditPolicyError as error:
            raise StagedSceneError("actor_edit_policy_rejected:"+str(error)) from error
        if action == "stationary_upper_body_prop_strict":
            from leg_core_guard import LegCoreError, check_thigh_cores
            try:
                anatomy["thigh_cores"] = check_thigh_cores(edit,source_pose,principal_index)
            except LegCoreError as error:
                raise StagedSceneError("actor_edit_policy_rejected:"+str(error)) from error
    guard=None
    if source_pose is not None:
        if principal_index is None:raise StagedSceneError('principal_attribution_required')
        from source_hand_mask_guard import check_stale_hand_coverage
        guard=check_stale_hand_coverage(source_pose,principal_index,edit)
        if guard['verdict']!='covered_for_replacement':
            raise StagedSceneError('source_hands_not_fully_editable:'+guard['reason'])
    return {'edit_fraction':round(fraction,5), 'protected_regions':len(protected_regions),
            'source_hand_coverage':guard, 'anatomy_lock':anatomy,
            'status':'preflight_only_qa_unverified'}


def attach_inpaint_to_klein_graph(original,*,source_upload,mask_upload):
    """Connect approved native Comfy nodes without changing model, seed or text.

    `original` is the caller's already prepared native Flux.2 Klein graph.
    Uploads must be unique, user-owned Comfy input names; this function
    never uploads files, contacts the network or mutates the original graph.
    """
    _name(source_upload);_name(mask_upload)
    if not isinstance(original,dict):raise StagedSceneError('missing_graph')
    g=deepcopy(original)
    expected={3:'VAELoader',10:'SamplerCustomAdvanced',11:'VAEDecode',12:'SaveImage'}
    if any(g.get(str(i),{}).get('class_type')!=t for i,t in expected.items()):
        raise StagedSceneError('not_native_klein_graph')
    if g['11'].get('inputs',{}).get('samples')!=['10',0]:
        raise StagedSceneError('unexpected_vae_decode_graph')
    if g['12'].get('inputs',{}).get('images')!=['11',0]:
        raise StagedSceneError('unexpected_publish_image_graph')
    if not isinstance(g['10'].get('inputs',{}).get('latent_image'),list):
        raise StagedSceneError('missing_original_latent_link')
    numeric=[int(k) for k in g if isinstance(k,str) and k.isdecimal()]
    if len(numeric)!=len(g):raise StagedSceneError('noncanonical_graph_ids')
    start=max(numeric)+1
    ids=[str(start+i) for i in range(5)]
    s,m,encoder,latent,composite=ids
    g[s]={'class_type':'LoadImage','inputs':{'image':source_upload}}
    g[m]={'class_type':'LoadImage','inputs':{'image':mask_upload}}
    g[encoder]={'class_type':'VAEEncode','inputs':{'pixels':[s,0],'vae':['3',0]}}
    g[latent]={'class_type':'SetLatentNoiseMask','inputs':{'samples':[encoder,0],'mask':[m,1]}}
    g[composite]={'class_type':'ImageCompositeMasked','inputs':{
        'destination':[s,0], 'source':['11',0], 'x':0,'y':0,
        'resize_source':False,'mask':[m,1]}}
    g['10']['inputs']['latent_image']=[latent,0]
    g['12']['inputs']['images']=[composite,0]
    return g,{'nodes':{'source':s,'mask':m,'encoder':encoder,'masked_latent':latent,
                       'composite':composite},
              'policy':'isolated_only_requires_full_visual_qa'}


def verify_output_preservation(source_png,output_png,inverse_alpha_png):
    """Fail if a completed CG changed even one fully locked original pixel.

    Partial alpha bands are intentionally permitted to blend. Exactly zero
    permissions (mask alpha=255) must be byte-identical in decoded RGB values.
    This check must run *before* full QA, and neither check implies the other.
    """
    from PIL import Image,ImageOps,ImageChops
    try:
        with Image.open(BytesIO(source_png)) as s, \
             Image.open(BytesIO(output_png)) as o, \
             Image.open(BytesIO(inverse_alpha_png)) as m:
            if min(s.size)<1 or s.size!=o.size or s.size!=m.size:
                raise StagedSceneError('output_dimensions_do_not_match_source')
            if m.format!='PNG' or m.mode!='RGBA':
                raise StagedSceneError('invalid_edit_permissions')
            before=s.convert('RGB');after=o.convert('RGB')
            edit=ImageOps.invert(m.getchannel('A'))
            locked=edit.point(lambda v:255 if v==0 else 0)
            if not locked.getbbox():raise StagedSceneError('no_fully_protected_pixels')
            changed=ImageChops.difference(before,after)
            if changed.getbbox() is None:return {'status':'strict_pixels_preserved',
                 'protected_pixel_count':sum(locked.histogram()[255:])}
            mismatch=Image.composite(changed,Image.new('RGB',before.size),locked)
            if mismatch.getbbox():
                raise StagedSceneError('protected_pixels_changed_in_output')
            return {'status':'strict_pixels_preserved',
                    'protected_pixel_count':locked.histogram()[255]}
    except (OSError,TypeError) as error:
        raise StagedSceneError('source_output_mask_unreadable') from error
