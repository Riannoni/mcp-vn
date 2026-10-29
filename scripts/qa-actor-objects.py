#!/usr/bin/env python3
"""Read-only Florence-2 object-localization experiment (shadow only).

Run in PC qa-shadow-venv, never from production vision daemon; annotations
and exact actor ROIs must be separately verified before using as a gate.
"""
import argparse
import json
import pathlib
import sys
import time
from PIL import Image
import torch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"worker"))
from actor_evidence import boxes_from_od,principal_spatial_observation

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("images",nargs="+",type=pathlib.Path)
    ap.add_argument("--contracts",type=pathlib.Path,help="JSON mapping filename to explicitly labeled actor regions")
    args=ap.parse_args()
    contracts=json.loads(args.contracts.read_text()) if args.contracts else {}
    torch.set_num_threads(5)
    from transformers import AutoProcessor,Florence2ForConditionalGeneration
    model_id="florence-community/Florence-2-base-ft"
    processor=AutoProcessor.from_pretrained(model_id,local_files_only=True)
    model=Florence2ForConditionalGeneration.from_pretrained(model_id,local_files_only=True).eval()
    for path in args.images:
        original=Image.open(path).convert("RGB")
        im=original.copy()
        im.thumbnail((640,640))
        start=time.monotonic()
        values=processor(images=im,text="<OD>",return_tensors="pt")
        with torch.inference_mode():
            raw=model.generate(**values,max_new_tokens=256,num_beams=1)
        desc=processor.batch_decode(raw,skip_special_tokens=False)[0]
        data=processor.post_process_generation(desc,task="<OD>",image_size=im.size)
        detections=data.get("<OD>",{})
        annotated=contracts.get(path.name,{})
        evidence=principal_spatial_observation(
            annotated.get("principals",[]),detections,im.size)
        print(json.dumps({
            "file":path.name,"detector_seconds":round(time.monotonic()-start,3),
            "person_box_count_after_dedup":len(boxes_from_od(detections,im.size)),
            "observation":evidence,
            "model":model_id},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
