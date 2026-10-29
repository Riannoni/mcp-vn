#!/usr/bin/env python3
"""CPU-only, read-only VLM candidate timing. No story mutations or uploads.

Usage: python qa-shadow-benchmark.py florence image1.png image2.png
       python qa-shadow-benchmark.py qwen image1.png image2.png
Output is JSON to stdout. Full candidate errors should not affect production.
"""
import argparse
import json
import os
import time
import pathlib
import statistics
import sys
from PIL import Image
import torch

MODELS={"florence":"florence-community/Florence-2-base-ft",
        "qwen":"Qwen/Qwen3.5-0.8B"}
PROMPT=("Describe only the visible setting, number of people, clothing, "
        "body positions and any physical contact with objects. "
        "Do not infer unseen details. Use two short factual sentences.")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("model",choices=MODELS)
    ap.add_argument("images",nargs="+",type=pathlib.Path)
    ap.add_argument("--tokens",type=int,default=100)
    opts=ap.parse_args()
    torch.set_num_threads(5)
    # Existing production VLM/ComfyUI are never imported or modified.
    from transformers import AutoProcessor
    name=MODELS[opts.model]
    started=time.monotonic()
    processor=AutoProcessor.from_pretrained(name,local_files_only=True)
    if opts.model=="florence":
        from transformers import Florence2ForConditionalGeneration
        model=Florence2ForConditionalGeneration.from_pretrained(
            name,dtype=torch.float32,local_files_only=True).eval()
    else:
        from transformers import AutoModelForMultimodalLM
        model=AutoModelForMultimodalLM.from_pretrained(
            name,dtype=torch.float32,local_files_only=True).eval()
    loading=round(time.monotonic()-started,3)
    results=[]
    for file in opts.images:
        if not file.is_file():raise FileNotFoundError(file)
        image=Image.open(file).convert("RGB")
        image.thumbnail((560,560),Image.Resampling.LANCZOS)
        started=time.monotonic()
        if opts.model=="florence":
            prompt="<MORE_DETAILED_CAPTION>"
            values=processor(images=image,text=prompt,return_tensors="pt")
        else:
            messages=[{"role":"user","content":[
                {"type":"image","image":image},
                {"type":"text","text":PROMPT}]}]
            values=processor.apply_chat_template(messages,
                add_generation_prompt=True,tokenize=True,
                return_dict=True,return_tensors="pt")
        with torch.inference_mode():
            generated=model.generate(**values,max_new_tokens=opts.tokens,
                do_sample=False)
        if opts.model=="florence":
            text=processor.batch_decode(generated,skip_special_tokens=False)[0]
            try:
                text=processor.post_process_generation(text,
                   task="<MORE_DETAILED_CAPTION>",image_size=image.size)
            except (ValueError,KeyError):
                pass
        else:
            n=values["input_ids"].shape[-1]
            text=processor.decode(generated[0][n:],skip_special_tokens=True)
        results.append({"file":file.name,"seconds":round(time.monotonic()-started,3),
                        "output":str(text)[:1200]})
        print("PROGRESS",opts.model,file.name,results[-1]["seconds"],flush=True,file=sys.stderr)
    samples=[r["seconds"] for r in results]
    print(json.dumps({"model":name,"load_seconds":loading,
        "median_seconds":round(statistics.median(samples),3),
        "results":results},ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
