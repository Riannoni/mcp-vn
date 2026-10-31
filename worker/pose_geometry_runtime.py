"""Lightweight Comfy DWPose-only extraction for post-render geometry QA.

This uses only the pose detector (no image-generation checkpoint). A geometry
match is diagnostic evidence and does not prove physical wall contact.
"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path

from pose_geometry_contract import inspect_approved_pose
from contact_geometry import inspect_contact_region

def verify_with_comfy(job,image_bytes,reference,comfy,output_dir,request,upload):
    root=reference["file"].parents[1]
    manifest=json.loads((root/"manifest.json").read_text())
    metadata=next((x for x in manifest if x.get("id")==reference["name"]),None)
    if metadata is None or not metadata.get("keypoints"):
        return {"verified":False,"reason":"approved_reference_keypoints_missing"}
    source=(root/str(metadata["keypoints"])).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        return {"verified":False,"reason":"invalid_reference_keypoints"}
    expected=json.loads(source.read_text())

    token=uuid.uuid4().hex[:12]
    prefix="vn_pose_qa_"+job["id"].replace("-","")[:12]+"_"+token
    image_name=upload(image_bytes,prefix+".png")
    graph={
        "1":{"class_type":"LoadImage","inputs":{"image":image_name}},
        "2":{"class_type":"DWPreprocessor","inputs":{
            "image":["1",0],"detect_body":"enable","detect_hand":"disable",
            "detect_face":"disable","resolution":768,
            "bbox_detector":"yolox_l.onnx",
            "pose_estimator":"dw-ll_ucoco_384.onnx",
            "scale_stick_for_xinsr_cn":"enable"}},
        "3":{"class_type":"SavePoseKpsAsJsonFile","inputs":{
            "pose_kps":["2",1],"filename_prefix":prefix}},
    }
    response=request(comfy,"/prompt","POST",{
        "prompt":graph,"client_id":"mcp-vn-pose-qa"},
        headers={"Idempotency-Key":"mcp-vn-pose-qa:"+prefix},timeout=25)
    prompt_id=response["prompt_id"]
    output=Path(output_dir)
    start=time.monotonic()
    while time.monotonic()-start<75:
        time.sleep(1.5)
        history=request(comfy,"/history/"+prompt_id,timeout=8)
        row=history.get(prompt_id)
        if not row:continue
        if row.get("status",{}).get("status_str")!="success":
            return {"verified":False,"reason":"dwpose_execution_failed"}
        files=sorted(output.glob(prefix+"*.json"),key=lambda x:x.stat().st_mtime)
        if not files:
            return {"verified":False,"reason":"dwpose_keypoints_missing"}
        path=files[-1]
        try:
            actual=json.loads(path.read_text())
        finally:
            path.unlink(missing_ok=True)
        contract=(job.get("spec") or {}).get("visual_contract") or {}
        principals=contract.get("principals") or []
        # Only a single explicit named principal can be attributed to a ROI.
        actor_region=(principals[0].get("region") if len(principals)==1
                      and isinstance(principals[0],dict) else None)
        verdict=inspect_approved_pose(expected,actual,actor_region=actor_region)
        contract=(job.get("spec") or {}).get("visual_contract") or {}
        contacts=contract.get("contacts") or []
        if len(contacts)==1 and contacts[0].get("target_region"):
            verdict["contact_roi"]=inspect_contact_region(actual,contacts[0])
        verdict["reference_id"]=reference["name"]
        verdict["duration_seconds"]=round(time.monotonic()-start,2)
        return verdict
    return {"verified":False,"reason":"dwpose_timeout"}
