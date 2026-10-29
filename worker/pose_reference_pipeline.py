"""Reference-photo -> DWPose -> reviewable ControlNet guide pipeline.

Source photos are fetched from Wikimedia Commons with license/source metadata.
Generated controls are DRAFTS until human-reviewed A/B renders are approved.
Never change the game save or automatically set approved=True.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HOST = os.getenv("VN_COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
DEFAULT_ROOT = Path.home() / ".local/share/mcp-vn/pose-references-v1"
USER_AGENT = "mcp-vn-pose-references/1.0 (personal research; photo attribution retained)"
CURATED = {
    "wall_push_side_01": {
        "title": "File:Full body workout with low impact 070912-M-HY785-004.jpg",
        "action": "palms_on_wall",
        "camera": "side",
        "description": "One person doing wall pushups; photograph from US Marines",
    },
    "wall_push_side_02": {
        "title": "File:Cardio workout off land 071012-M-HY785-003.jpg",
        "action": "palms_on_wall",
        "camera": "side",
        "description": "Another person doing wall pushups; US Marines",
    },
    "bend_forward_01": {
        "title": "File:Advanced version of uttanasana.jpg",
        "action": "bend_forward",
        "camera": "side_or_oblique",
        "description": "Standing forward bend yoga practice, CC BY-SA",
    },
}
APPROVED_LICENSES = ("Public domain", "CC BY", "Creative Commons Attribution", "cc-by", "PD-")
# Personal study references only: the photos are not redistributed and their
# reuse licence has not been independently verified. The *derived pose guide*
# may enter local approved state only after independent A/B and review.
EXTERNAL_CANDIDATES = {
    "wall_push_correct_side_a": {
        "url": "https://static.bodyspec.com/tr/e1/c1/e1c1f503c38f908b?f=jpg&h=683&w=1024",
        "page": "https://www.bodyspec.com/blog/post/tabata_training_the_4minute_workout_protocol",
        "action": "palms_on_wall", "camera": "side"},
    "wall_push_correct_side_b": {
        "url": "https://storage.googleapis.com/jacksonh/1/Five-Minute-ExercisesFeatured.webp",
        "page": "https://jacksonhealth.org/five-minute-exercises-to-help-lower-blood-pressure/",
        "action": "palms_on_wall", "camera": "side"},
    "wall_push_rear_oblique_01": {
        "url":"https://www.fitmetsteffie.nl/cache/media/2365698085c4b146files-Lijst-oefeningen-push-up-wall.jpg",
        "page":"https://www.fitmetsteffie.nl/nl/oefeningen/opdrukken-tegen-de-muur.html",
        "action":"palms_on_wall","camera":"rear"},
    "wall_push_rear_oblique_02": {
        "url":"https://cdn.shopify.com/s/files/1/0267/3351/0727/files/wall-push-ups-buoy_1024x1024.jpg?v=1736870521",
        "page":"https://justaddbuoy.com/blogs/pots-resources/low-impact-exercises-for-pots",
        "action":"palms_on_wall","camera":"rear"},
    "hip_hinge_side_01": {
        "url":"https://yogaselection.com/wp-content/uploads/2024/05/ardha-uttanasana.png",
        "page":"https://yogaselection.com/10-essential-iyengar-yoga-poses-for-beginners/",
        "action":"palms_on_wall_hip_hinge","camera":"side"},
    "hip_hinge_side_02": {
        "url":"https://cdn.shopify.com/s/files/1/0589/6621/2814/files/AmyIppolitiHandsattheWallCorrect.jpg",
        "page":"https://www.toesox.com/blogs/toe-sox/5-steps-to-touching-your-toes",
        "action":"palms_on_wall_hip_hinge","camera":"side"},
    "hip_hinge_rear_oblique_01": {
        "url":"https://media.graphassets.com/resize%3Dfit%3Aclip%2Cheight%3A350%2Cwidth%3A600/resize%3Dwidth%3A1080%2Cheight%3A1080/25CPNVtR9SIrJyJYSnqb",
        "page":"https://www.myyogateacher.com/yoga-asana/uttanasana",
        "action":"palms_on_wall_hip_hinge","camera":"rear"},
    "hip_hinge_rear_oblique_02": {
        "url":"https://rmyyrqiqfdzgaycwjrqc.supabase.co/storage/v1/object/public/blog-images/posts/wall-yoga-poses/5cc71324df5b4195bf8b06ab7f67e063.jpg",
        "page":"https://better5.com/wall-yoga-poses",
        "action":"palms_on_wall_hip_hinge","camera":"rear"},
}


def _get_json(url: str, timeout: int = 30):
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as response:
        return json.load(response)


def _post_json(url: str, obj, timeout: int = 30):
    from urllib.request import Request
    raw = json.dumps(obj).encode()
    with urlopen(Request(url, data=raw,
                         headers={"Content-Type":"application/json",
                                  "User-Agent":USER_AGENT}), timeout=timeout) as response:
        return json.load(response)


def _download(url: str, limit: int = 20_000_000):
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=40) as r:
        content = r.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Reference image too large")
    return content


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_text(metadata, key):
    raw = metadata.get(key, {})
    value = raw.get("value", "") if isinstance(raw, dict) else str(raw)
    return re.sub(r"<[^>]*>", "", value).strip()


def download_references(root=DEFAULT_ROOT):
    root = Path(root)
    (root/"refs").mkdir(parents=True, exist_ok=True)
    existing_path=root/"manifest.json"
    manifest=json.loads(existing_path.read_text()) if existing_path.exists() else []
    existing={str(item.get("id")) for item in manifest}
    for name, info in CURATED.items():
        if name in existing:
            print("SKIP_EXISTING_REFERENCE",name,flush=True)
            continue
        params = urlencode({
            "action":"query", "titles":info["title"], "prop":"imageinfo",
            "iiprop":"url|extmetadata", "iiurlwidth":"1200", "format":"json",
        })
        data = _get_json(COMMONS_API+"?"+params)
        page = next(iter(data["query"]["pages"].values()))
        ii = page["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        license_name = _safe_text(meta,"LicenseShortName")
        usage = _safe_text(meta,"UsageTerms")
        if not any(s.lower() in (license_name+" "+usage).lower() for s in APPROVED_LICENSES):
            raise ValueError(f"Unapproved source license for {name}: {license_name}")
        original = _download(ii.get("thumburl") or ii["url"])
        tmp = root/"refs"/(name+".jpg")
        import io
        with Image.open(io.BytesIO(original)) as img:
            rgb = ImageOps.exif_transpose(img).convert("RGB")
            rgb.thumbnail((1200,1200))
            rgb.save(tmp, format="JPEG", quality=91)
            w,h = rgb.size
        manifest.append({
            "id": name, "source_title": info["title"], "source_page":
                "https://commons.wikimedia.org/wiki/"+info["title"].replace("File:","File:").replace(" ","_"),
            "source_url": ii["url"],
            "source_license": license_name, "author": _safe_text(meta,"Artist"),
            "license_url": _safe_text(meta,"LicenseUrl"),
            "action": info["action"],"camera": info["camera"],
            "description":info["description"],"reference": "refs/"+name+".jpg",
            "reference_sha256":_sha(tmp.read_bytes()), "dimensions":[w,h],
            "guide": None, "keypoints": None,
            "extraction_status":"pending", "status":"draft", "approved":False,
        })
        print("REF", name, w, h, license_name, flush=True)
    for name,item in EXTERNAL_CANDIDATES.items():
        if name in existing:
            print("SKIP_EXISTING_REFERENCE",name,flush=True)
            continue
        raw=_download(item["url"])
        import io
        with Image.open(io.BytesIO(raw)) as img:
            rgb=ImageOps.exif_transpose(img).convert("RGB")
            rgb.thumbnail((1200,1200))
            out=root/"refs"/(name+".jpg")
            rgb.save(out,format="JPEG",quality=91)
            width,height=rgb.size
        manifest.append({
            "id":name,"source_title":"Photographic pose reference",
            "source_page":item["page"],"source_url":item["url"],
            "source_license":"unverified_external_evaluation_only",
            "usage_scope":"private_local_pose_review_no_photo_redistribution",
            "author":"external publisher (unverified)",
            "action":item["action"],"camera":item["camera"],
            "description":"Adult with palms on a vertical wall; shot direction: "+item["camera"],
            "reference":"refs/"+name+".jpg","reference_sha256":_sha(out.read_bytes()),
            "dimensions":[width,height],"guide":None,"keypoints":None,
            "extraction_status":"pending","status":"draft","approved":False,
        })
        print("REF_EXTERNAL_LOCAL",name,width,height,flush=True)
    _atomic_json(root/"manifest.json",manifest)
    return manifest


def _atomic_json(file, data):
    file=Path(file)
    file.parent.mkdir(parents=True,exist_ok=True)
    temporary=file.with_name(file.name+".tmp")
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    os.replace(temporary,file)


def _upload_comfy(image: Path):
    import requests
    with image.open("rb") as fh:
        r=requests.post(HOST+"/upload/image",
            files={"image":(image.name,fh,"image/jpeg")},
            data={"overwrite":"true","type":"input"},timeout=40)
    r.raise_for_status()
    return r.json()["name"]


def _node_info(node):
    return _get_json(HOST+"/object_info/"+node,timeout=15).get(node)


def extract_guides(root=DEFAULT_ROOT):
    root=Path(root)
    manifest=json.loads((root/"manifest.json").read_text())
    if not _node_info("DWPreprocessor"):
        raise RuntimeError("ComfyUI DWPose preprocessor unavailable")
    import requests
    (root/"guides").mkdir(parents=True,exist_ok=True)
    (root/"extractions").mkdir(parents=True,exist_ok=True)
    for record in manifest:
        if record.get("approved"):
            print("SKIP_APPROVED_REFERENCE",record["id"],flush=True)
            continue
        ref=root/record["reference"]
        if _sha(ref.read_bytes())!=record["reference_sha256"]:
            raise ValueError("Source reference modified: "+record["id"])
        upload=_upload_comfy(ref)
        prefix="mcp_vn_dwpose_"+record["id"]
        graph={
            "1":{"class_type":"LoadImage","inputs":{"image":upload}},
            "2":{"class_type":"DWPreprocessor","inputs":{
                "image":["1",0],"detect_body":"enable","detect_hand":"enable",
                "detect_face":"disable","resolution":768,
                "bbox_detector":"yolox_l.onnx",
                "pose_estimator":"dw-ll_ucoco_384.onnx",
                "scale_stick_for_xinsr_cn":"enable"}},
            "3":{"class_type":"SaveImage","inputs":{"images":["2",0],
                "filename_prefix":prefix}},
            "4":{"class_type":"SavePoseKpsAsJsonFile","inputs":{
                "pose_kps":["2",1],"filename_prefix":prefix+"_keypoints"}},
        }
        response=_post_json(HOST+"/prompt",{"prompt":graph,"client_id":"vn-pose-ref-v1"},timeout=35)
        if response.get("node_errors"):
            raise RuntimeError(str(response["node_errors"]))
        key=response["prompt_id"]
        deadline=time.monotonic()+320
        while time.monotonic()<deadline:
            time.sleep(3)
            history=_get_json(HOST+"/history/"+key,timeout=20).get(key)
            if not history:continue
            status=history.get("status",{})
            if status.get("status_str")=="error":
                raise RuntimeError(str(status.get("messages",[]))[-1600:])
            images=(history.get("outputs",{}).get("3",{}).get("images") or [])
            if not images:
                raise RuntimeError("DWPose produced no image: "+record["id"])
            image=images[0]
            params=urlencode({"filename":image["filename"],
                "subfolder":image.get("subfolder",""),"type":image.get("type","output")})
            data=_download(HOST+"/view?"+params)
            target=root/"guides"/(record["id"]+".png")
            target.write_bytes(data)
            with Image.open(target) as im:
                rgb=im.convert("RGB")
                # SDXL pose guide must align to a single 1216x704 story frame.
                canvas=Image.new("RGB",(1216,704),(0,0,0))
                rgb.thumbnail((1216,704),Image.Resampling.LANCZOS)
                canvas.paste(rgb,((1216-rgb.width)//2,(704-rgb.height)//2))
                canvas.save(target)
            record["guide"]="guides/"+record["id"]+".png"
            record["guide_sha256"]=_sha(target.read_bytes())
            record["extraction_status"]="generated"
            record["comfy_prompt_id"]=key
            # DWPose POSE_KEYPOINT output can be read from history metadata
            # if ComfyUI exposes it, but never forge COCO coordinates.
            keypoints = sorted((Path.home()/".local/share/mcp-vn-comfy/output").glob(prefix+"_keypoints_*.json"),key=lambda f:f.stat().st_mtime)
            record["keypoints"]=None
            if keypoints:
                payload=json.loads(keypoints[-1].read_text())
                # Comfy exposes a list of per-frame pose dictionaries.
                poses=payload if isinstance(payload,list) else [payload]
                kps=((poses[0].get("people") or [{}])[0].get("pose_keypoints_2d") or []) if poses else []
                values=[kps[i+2] for i in range(0,min(len(kps),54),3)]
                confident=sum(float(v)>=0.25 for v in values)
                dest=root/"extractions"/(record["id"]+".json")
                dest.write_text(json.dumps(payload,indent=2))
                record["keypoints"]="extractions/"+record["id"]+".json"
                record["body_joints_confident"]=confident
                record["extraction_status"]=("generated" if confident>=12 else "rejected_low_keypoint_coverage")
                if confident<12: record["status"]="rejected"
                print("JOINTS",record["id"],confident,flush=True)
            else:
                record["extraction_status"]="rejected_no_keypoint_metadata"
                record["status"]="rejected"
            print("EXTRACTED",record["id"],target.stat().st_size,flush=True)
            _atomic_json(root/"manifest.json",manifest)
            break
        else:
            raise TimeoutError("DWPose inference took too long: "+record["id"])
    return manifest


def validate_manifest(root=DEFAULT_ROOT):
    root=Path(root)
    manifest=json.loads((root/"manifest.json").read_text())
    for record in manifest:
        assert record["status"] in ("draft","reviewed","approved","rejected")
        assert not record["approved"] or record["status"]=="approved"
        ref=root/record["reference"]
        assert ref.is_file() and _sha(ref.read_bytes())==record["reference_sha256"]
        if record["guide"]:
            guide=root/record["guide"]
            assert guide.is_file() and _sha(guide.read_bytes())==record["guide_sha256"]
            with Image.open(guide) as im: assert im.size==(1216,704)
        if record["approved"]:
            assert record["status"]=="approved" and record.get("review",{}).get("ab_better") is True
    print("MANIFEST_VALID",len(manifest),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("operation",choices=("download","extract","validate"))
    parser.add_argument("--root",default=str(DEFAULT_ROOT))
    opts=parser.parse_args()
    if opts.operation=="download":download_references(opts.root)
    elif opts.operation=="extract":extract_guides(opts.root)
    else:validate_manifest(opts.root)
