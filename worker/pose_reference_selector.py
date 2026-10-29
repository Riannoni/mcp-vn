"""Fail-closed selection of human-reviewed DWPose pose guides.

No reference is trusted merely because a matching file exists. The manifest
requires matching prompt semantics, a source hash, a guide hash and explicit
A/B approval. This avoids silently forcing a mismatched camera/viewpoint.
"""
from pathlib import Path
import hashlib
import json
import os

DEFAULT_ROOT=Path.home()/".local/share/mcp-vn/pose-references-v1"

def scene_action_key(prompt, characters=None):
    s=str(prompt or "").lower()
    rear=any(x in s for x in ("rear view","from behind","view from the back", "rear three-quarter", "three-quarter rear", "back three-quarter"))
    side=any(x in s for x in ("side view","from the side","profile view"))
    wall=any(x in s for x in ("stone wall","brick wall","against the wall",
        "palms on the wall","hands on the wall","wall push-up","wall pushup"))
    palms=any(x in s for x in ("both palms","both hands","palms braced",
        "hands braced","hands on the wall","palms on the wall"))
    bending=any(x in s for x in ("leaning forward","leans forward",
        "bending forward","bent forward","inclines toward the wall","wall push"))
    hip_hinge=any(x in s for x in (
        "bent at the waist","bend at the waist","bends at the waist",
        "hinged at the hips","hinges at the hips","bends forward at the hips", "bending forward at the hips",
        "torso horizontal","folded forward at the waist",
        "folds forward at the waist","forward fold",
        "bending forward at the waist", "leaning forward at the waist",
        "hip hinge", "hip-hinge",
    ))
    if wall and palms and bending:
        action="palms_on_wall_hip_hinge" if hip_hinge else "palms_on_wall"
        if rear:return (action,"rear")
        if side:return (action,"side")
    if (any(x in s for x in ("forward bend","bent forward","bending forward")) and
        side and not wall):
        return ("bend_forward","side_or_oblique")
    return (None,None)

def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def choose_approved_reference(prompt,root=DEFAULT_ROOT):
    root=Path(root).resolve()
    manifest=root/"manifest.json"
    if not manifest.is_file():
        return None,"no_manifest"
    action,camera=scene_action_key(prompt)
    if action is None:return None,"no_exact_action"
    try:
        entries=json.loads(manifest.read_text())
    except (OSError,ValueError):
        return None,"invalid_manifest"
    for item in entries:
        if item.get("action")!=action or item.get("camera")!=camera:
            continue
        if item.get("approved") is not True or item.get("status")!="approved":
            continue
        if item.get("extraction_status")!="generated" or int(item.get("body_joints_confident",0))<12:
            continue
        review=item.get("review") or {}
        if not (review.get("qa_passed") is True and
                review.get("ab_better") is True and
                review.get("reviewer") and review.get("reviewed_at")):
            continue
        try:
            file=root/str(item["guide"])
            file=file.resolve(strict=True)
            if not file.is_relative_to(root):
                return None,"unsafe_path"
            if file.suffix!=".png":
                return None,"invalid_extension"
            if _digest(file)!=item["guide_sha256"]:
                return None,"guide_hash_mismatch"
            src=(root/str(item["reference"])).resolve(strict=True)
            if not src.is_relative_to(root):
                return None,"unsafe_reference"
            if _digest(src)!=item["reference_sha256"]:
                return None,"source_hash_mismatch"
            from PIL import Image
            with Image.open(file) as im:
                if im.size!=(1216,704):
                    return None,"invalid_guide_size"
            return {"name":item["id"],"file":file,"source":src}, "approved"
        except (KeyError,OSError,ValueError):
            return None,"invalid_approved_asset"
    return None,"no_approved_exact_match"
