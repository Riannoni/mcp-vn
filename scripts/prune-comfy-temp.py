#!/usr/bin/env python3
"""Conservative maintenance for mcp-vn-only ComfyUI temporary files.

Default DRY RUN. No access to canonical server assets; no recursive deletion.
Rejects symlinks and unexpected paths. Never prune while ComfyUI is busy.
"""
import argparse
import json
import os
import pathlib
import time
import urllib.request

PREFIXES=("mcp_vn_",)
EXTENSIONS={".png",".jpg",".webp",".mp4",".json"}
def queue_idle(url):
    with urllib.request.urlopen(url.rstrip("/")+"/queue",timeout=5) as response:
        payload=json.load(response)
    return not payload.get("queue_running") and not payload.get("queue_pending")
def candidates(root,days,now):
    root=pathlib.Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Comfy temp directory must be an existing real directory")
    for f in root.iterdir():
        if (f.is_symlink() or not f.is_file() or
            not f.name.startswith(PREFIXES) or f.suffix.lower() not in EXTENSIONS):
            continue
        st=f.stat(follow_symlinks=False)
        if st.st_mtime<=now-days*86400:
            yield f,st.st_size
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--days",type=int,default=30)
    p.add_argument("--limit",type=int,default=200)
    p.add_argument("--comfy",default="http://127.0.0.1:8188")
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    if args.days<14 or not 1<=args.limit<=500:
        raise ValueError("days >=14 and 1<=limit<=500 required")
    home=(pathlib.Path.home()/".local/share/mcp-vn-comfy").resolve()
    roots=[pathlib.Path(args.input).resolve(),pathlib.Path(args.output).resolve()]
    if any(root not in (home/"input",home/"output") for root in roots) or roots[0]==roots[1]:
        raise ValueError("Only fixed ComfyUI input/output directories are allowed")
    if not queue_idle(args.comfy):
        raise RuntimeError("ComfyUI busy, maintenance not allowed")
    picked=[]
    for root in roots:
        picked.extend(candidates(root,args.days,time.time()))
    picked.sort(key=lambda p:p[0].stat().st_mtime)
    picked=picked[:args.limit]
    if args.apply and not queue_idle(args.comfy):
        raise RuntimeError("ComfyUI became busy; no deletions made")
    removed=0
    for file,size in picked:
        if args.apply:
            # Fresh stat just before unlink reduces time-of-check/time-of-use
            # surprises; user runtime owns these private temp paths.
            if file.is_symlink():continue
            file.unlink()
        removed+=size
    print(json.dumps({"mode":"apply" if args.apply else "dry-run",
        "files":len(picked),"bytes":removed,"days":args.days},sort_keys=True))
if __name__=="__main__":
    main()
