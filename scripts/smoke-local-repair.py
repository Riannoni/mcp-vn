#!/usr/bin/env python3
"""Run an isolated, noncanonical SDXL inpaint smoke on a saved neutral CG.
No game job, saved-game asset, or worker API mutation. Requires idle ComfyUI.
"""
import hashlib
import io
import json
import os
import sys
import tempfile
import uuid
import urllib.request
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from local_repair import archive_rejected_candidate,apply_inpaint_graph,cleanup

COMFY="http://127.0.0.1:8188"
ROOT=Path.home()/".local/share/mcp-vn"
IMAGE=ROOT/"benchmark-models"/"zimage.png"
def get(path):
    return json.load(urllib.request.urlopen(COMFY+path,timeout=10))
def upload(raw,name):
    import uuid
    boundary="----vnsmoke"+uuid.uuid4().hex
    headers={"Content-Type":"multipart/form-data; boundary="+boundary}
    prefix=(f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
            'Content-Type: image/png\r\n\r\n').encode()
    suffix=(f'\r\n--{boundary}--\r\n').encode()
    body=prefix+raw+suffix
    req=urllib.request.Request(COMFY+"/upload/image",data=body,headers=headers)
    result=json.load(urllib.request.urlopen(req,timeout=20))
    return result["name"]
def main():
    queue=get("/queue")
    if queue.get("queue_running") or queue.get("queue_pending"):
        raise RuntimeError("ComfyUI is busy; smoke test aborted without generation")
    source=Image.open(IMAGE).convert("RGB")
    raw=IMAGE.read_bytes()
    jobid=str(uuid.uuid4())
    job={"id":jobid,"kind":"scene","style":"realistic","attempts":1,
         "spec":{"max_attempts":3,"resolution":list(source.size),
                 "visual_contract":{"principals":[{"name":"Guide",
                    "region":[.12,.22,.24,.43]}]}}}
    with tempfile.TemporaryDirectory(prefix="vn-repair-smoke-") as tmp:
        os.environ["VN_REJECTED_REPAIR_DIR"]=tmp
        assert archive_rejected_candidate(job,raw,[],"wardrobe")
        retry={**job,"attempts":2,"error":"Wardrobe mismatch"}
        graph={
         "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"CyberRealisticPony_V18.0_F16.safetensors"}},
         "3":{"class_type":"CLIPTextEncode","inputs":{"clip":["1",1],
             "text":"score_9, realistic medieval market, woman wearing clean bright green cloak"}},
         "4":{"class_type":"CLIPTextEncode","inputs":{"clip":["1",1],
             "text":"watermark, wrong outfit, extra limbs, split-screen"}},
         "5":{"class_type":"KSampler","inputs":{"model":["1",0],"positive":["3",0],
             "negative":["4",0],"latent_image":["2",0],"seed":20261029,
             "steps":10,"cfg":5,"sampler_name":"dpmpp_2m",
             "scheduler":"karras","denoise":1.0}},
         "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
         "7":{"class_type":"SaveImage","inputs":{"images":["6",0],
             "filename_prefix":"vn_qa_inpaint_smoke_"+jobid}}}
        assert apply_inpaint_graph(retry,graph,["1",2],upload)
        result=get("/queue")
        if result.get("queue_running") or result.get("queue_pending"):
            raise RuntimeError("ComfyUI became busy; aborted")
        req=urllib.request.Request(COMFY+"/prompt",
            data=json.dumps({"prompt":graph,"client_id":"qa-inpaint-smoke"}).encode(),
            headers={"Content-Type":"application/json"})
        output=json.load(urllib.request.urlopen(req,timeout=25))
        token=output["prompt_id"]
        print("SUBMITTED",token,flush=True)
        import time
        for _ in range(80):
            time.sleep(1)
            h=get("/history/"+token)
            if token not in h:continue
            status=h[token].get("status",{})
            if status.get("status_str")!="success":
                raise RuntimeError("ComfyUI inpaint failed: "+str(status)[:900])
            files=h[token]["outputs"]["7"]["images"]
            info=files[0]
            outpath=ROOT/"mcp-vn-comfy"/"output"/info.get("subfolder","")/info["filename"]
            # Comfy output directory is outside game assets; never attach to session.
            if not outpath.is_file():
                outpath=Path.home()/".local/share/mcp-vn-comfy/output"/info["filename"]
            result=Image.open(outpath).convert("RGB")
            assert result.size==source.size,(result.size,source.size)
            patch=ImageChops.difference(source,result)
            outside=Image.new("L",source.size,255)
            from PIL import ImageDraw
            x,y,w,h=(.12,.22,.24,.43)
            ImageDraw.Draw(outside).rectangle(
                (int(x*source.width)-20,int(y*source.height)-20,
                 int((x+w)*source.width)+20,int((y+h)*source.height)+20),fill=0)
            outside_change=sum(ImageStat.Stat(patch,mask=outside).mean)
            print("SMOKE_PASS",json.dumps({"resolution":result.size,
                   "outside_mask_mae_rgb_sum":round(outside_change,3),
                   "output_sha256":hashlib.sha256(outpath.read_bytes()).hexdigest()[:16]}),
                  flush=True)
            outpath.unlink(missing_ok=True)
            cleanup(retry)
            return
        raise TimeoutError("Timed out waiting for shadow inpaint")
if __name__=="__main__":main()
