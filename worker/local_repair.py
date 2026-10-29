"""Conservative targeted inpainting of a *rejected* candidate, never an approved frame.

The region must be derived from a bounded, explicit actor/contact ROI or
the measured sprite alpha bounds. All repaired output is run through the
regular full QA; local repair is never a validation bypass.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import re
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

REPAIR_KINDS={"identity","wardrobe","physical_contact"}
MAX_REGION_AREA=.36
MAX_SOURCE_BYTES=18*1024*1024

def _region(values):
    if (not isinstance(values,(list,tuple)) or len(values)!=4 or
        any(isinstance(x,bool) or not isinstance(x,(float,int)) for x in values)):
        return None
    x,y,w,h=map(float,values)
    if not(0<=x<1 and 0<=y<1 and 0<w<=1 and 0<h<=1
           and x+w<=1.00001 and y+h<=1.00001 and w*h<=MAX_REGION_AREA):
        return None
    return [round(x,5),round(y,5),round(w,5),round(h,5)]

def _sprite_region(kind,image):
    rgba=image.convert("RGBA")
    bbox=rgba.getchannel("A").point(lambda v:255 if v>90 else 0).getbbox()
    if not bbox:return None
    left,top,right,bottom=bbox
    w,h=image.size
    cw=right-left;ch=bottom-top
    if kind=="identity":
        # Approximate head from upper part of *detected foreground*.
        region=[(left+cw*.18)/w,top/h,cw*.64/w,ch*.26/h]
    else:
        # Torso/clothing; never replace the full foreground automatically.
        region=[(left+cw*.12)/w,(top+ch*.22)/h,cw*.76/w,ch*.40/h]
    return _region(region)

def choose_repair_region(job,image,category):
    """No automatic guessing of which named actor in a multi-actor scene."""
    spec=job.get("spec") or {}
    if category not in REPAIR_KINDS:return None
    if job.get("style")=="animation":return None # non-SDXL model
    if job.get("kind")=="sprite":
        if category=="identity" and not spec.get("face_asset"):return None
        return _sprite_region(category,image)
    if job.get("kind") not in ("scene","local_cg"):return None
    contract=spec.get("visual_contract") or {}
    people=contract.get("principals") or []
    if category=="physical_contact":
        contacts=contract.get("contacts") or []
        return (_region(contacts[0].get("target_region"))
                if len(contacts)==1 and isinstance(contacts[0],dict) else None)
    if len(people)!=1:return None
    return _region(people[0].get("region"))

def _cache_root():
    root=Path(os.environ.get("VN_REJECTED_REPAIR_DIR",
        str(Path.home()/".local/share/mcp-vn/qa-rejected")))
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(root,0o700)
    return root

def _paths(job):
    jobid=str(job.get("id") or "")
    if not re.fullmatch(r"[a-f0-9-]{36}",jobid):return None
    root=_cache_root()
    return root/(jobid+".png"),root/(jobid+".json")

def cleanup(job):
    pair=_paths(job)
    if pair:
        for path in pair:path.unlink(missing_ok=True)

def archive_rejected_candidate(job,raw,reasons,category):
    """Store only on retries; a rejected image is sensitive and never in Git."""
    if (category not in REPAIR_KINDS or job.get("attempts",1)>=
        (job.get("spec") or {}).get("max_attempts",3) or
        not raw or len(raw)>MAX_SOURCE_BYTES):
        return False
    pair=_paths(job)
    if not pair:return False
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            roi=choose_repair_region(job,image,category)
    except (OSError,ValueError):return False
    if not roi:return False
    png,metadata=pair
    record={"version":1,"attempt":int(job.get("attempts",1)),
            "category":category,"roi":roi,"sha256":hashlib.sha256(raw).hexdigest()}
    suffix="."+uuid.uuid4().hex+".tmp"
    try:
        temporary=png.with_name(png.name+suffix)
        with open(temporary,"xb") as f:
            os.chmod(temporary,0o600)
            f.write(raw)
        os.replace(temporary,png)
        temporary=metadata.with_name(metadata.name+suffix)
        with open(temporary,"x",encoding="utf-8") as f:
            os.chmod(temporary,0o600)
            json.dump(record,f)
        os.replace(temporary,metadata)
    finally:
        for q in (png.with_name(png.name+suffix),metadata.with_name(metadata.name+suffix)):
            q.unlink(missing_ok=True)
    return True

def load_candidate(job,category):
    if category not in REPAIR_KINDS or int(job.get("attempts",1))<2:
        return None
    pair=_paths(job)
    if not pair:return None
    png,metadata=pair
    if not png.is_file() or not metadata.is_file():return None
    try:
        info=json.loads(metadata.read_text())
        raw=png.read_bytes()
        if (len(raw)>MAX_SOURCE_BYTES or info.get("version")!=1 or
            info.get("category")!=category or
            info.get("attempt")!=int(job["attempts"])-1 or
            hashlib.sha256(raw).hexdigest()!=info.get("sha256")):
            return None
        region=_region(info.get("roi"))
        if not region:return None
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.size!=tuple((job.get("spec") or {}).get("resolution") or ()):
                return None
        return raw,region
    except (OSError,ValueError,TypeError,KeyError):
        return None

def mask_source(raw,region):
    """RGBA alpha hole is a Comfy LoadImage MASK (white where editable)."""
    with Image.open(io.BytesIO(raw)) as img:
        img.load()
        rgb=img.convert("RGB")
    w,h=rgb.size
    x,y,rw,rh=region
    alpha=Image.new("L",(w,h),255)
    ImageDraw.Draw(alpha).rectangle(
        (int(x*w),int(y*h),int((x+rw)*w),int((y+rh)*h)),fill=0)
    # Feather mask edges to avoid a visible rectangular seam.
    radius=max(3,min(12,round(min(w,h)*.009)))
    alpha=alpha.filter(ImageFilter.GaussianBlur(radius))
    rgba=rgb.convert("RGBA")
    rgba.putalpha(alpha)
    out=io.BytesIO()
    rgba.save(out,format="PNG")
    return out.getvalue()

def apply_inpaint_graph(job,graph,vae_ref,upload):
    category=str(job.get("error_category") or "")
    if not category:
        from render_retry import retry_plan
        category=retry_plan(job)["category"]
    candidate=load_candidate(job,category)
    if candidate is None:return False
    raw,region=candidate
    if not graph.get("5") or not graph.get("6") or not graph.get("7"):
        return False
    masked=mask_source(raw,region)
    name=upload(masked,"mcp_vn_repair_"+job["id"]+".png")
    graph["90"]={"class_type":"LoadImage","inputs":{"image":name}}
    graph["91"]={"class_type":"VAEEncodeForInpaint","inputs":{
        "pixels":["90",0],"vae":vae_ref,"mask":["90",1],"grow_mask_by":6}}
    graph["5"]["inputs"]["latent_image"]=["91",0]
    graph["5"]["inputs"]["denoise"]=.68
    graph["92"]={"class_type":"ImageCompositeMasked","inputs":{
        "destination":["90",0],"source":["6",0],"x":0,"y":0,
        "resize_source":False,"mask":["90",1]}}
    graph["7"]["inputs"]["images"]=["92",0]
    return True
