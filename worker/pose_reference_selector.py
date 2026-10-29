"""Fail-closed selection of human-reviewed DWPose pose guides.

No reference is trusted merely because a matching file exists. The manifest
requires matching prompt semantics, a source hash, a guide hash and explicit
A/B approval. This avoids silently forcing a mismatched camera/viewpoint.
"""
from pathlib import Path
import hashlib
import json
import os
from scene_action_contract import scene_action_key, resolve_scene_action

DEFAULT_ROOT=Path.home()/".local/share/mcp-vn/pose-references-v1"

def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def choose_approved_reference(prompt,root=DEFAULT_ROOT,spec=None):
    root=Path(root).resolve()
    manifest=root/"manifest.json"
    if not manifest.is_file():
        return None,"no_manifest"
    contract=(resolve_scene_action({**spec,"prompt":prompt},prompt)
              if isinstance(spec,dict) else
              resolve_scene_action({"composition":"neural_story",
                 "characters":[{"name":"single adult"}],"prompt":prompt}))
    action,camera=contract["action"],contract["camera"]
    if action is None:return None,"no_exact_action"
    if camera is None:return None,"camera_missing_or_ambiguous"
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
