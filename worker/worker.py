#!/usr/bin/env python3
"""Private ComfyUI agent. Pulls jobs from home server; PC needs no inbound ports."""
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SERVER = os.environ.get("VN_SERVER", "http://192.168.50.29:3100").rstrip("/")
TOKEN = os.environ["VN_WORKER_TOKEN"]
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
OUTPUT = Path(os.environ.get("COMFY_OUTPUT", str(Path.home()/".local/share/mcp-vn-comfy/output")))
STYLES = {
    "anime": ("animagine-xl-4.0-opt.safetensors", 25, 6.0),
    "semireal": ("DreamShaperXL_Turbo_v2_1.safetensors", 10, 2.5),
    "realistic": ("RealVisXL_V5.0_fp16.safetensors", 28, 5.5),
    "poster": ("Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors", 30, 5.0),
}
def request(base, path, method="GET", data=None, headers=None, timeout=15):
    h=dict(headers or {})
    if base == SERVER: h["Authorization"]="Bearer "+TOKEN
    if data is not None and "Content-Type" not in h: h["Content-Type"]="application/json"
    raw=json.dumps(data).encode() if data is not None and not isinstance(data,bytes) else data
    req=Request(base+path, data=raw, headers=h, method=method)
    with urlopen(req,timeout=timeout) as result:
        payload=result.read()
        return json.loads(payload) if "json" in result.headers.get("Content-Type","") else payload
def image_graph(job):
    model,steps,cfg=STYLES[job["style"]]
    kind=job["kind"]
    w,h=(1216,704) if kind=="background" else ((832,1216) if kind=="sprite" else (1024,768))
    prompt=job["prompt"]
    if job["style"]=="anime": prompt="masterpiece, best quality, anime visual novel art, "+prompt
    elif job["style"]=="semireal": prompt="cinematic semi-realistic 2.5D illustration, detailed lighting, "+prompt
    elif job["style"]=="realistic": prompt="photorealistic, realistic skin, cinematic photograph, "+prompt
    graph={
      "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":model}},
      "2":{"class_type":"EmptyLatentImage","inputs":{"width":w,"height":h,"batch_size":1}},
      "3":{"class_type":"CLIPTextEncode","inputs":{"clip":["1",1],"text":prompt}},
      "4":{"class_type":"CLIPTextEncode","inputs":{"clip":["1",1],"text":"bad quality, deformed, disfigured, watermark, logo, text, child, underage"}},
      "5":{"class_type":"KSampler","inputs":{"model":["1",0],"positive":["3",0],"negative":["4",0],
         "latent_image":["2",0],"seed":int.from_bytes(os.urandom(6),"big"),"steps":steps,
         "cfg":cfg,"sampler_name":"euler","scheduler":"normal","denoise":1}},
      "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
      "7":{"class_type":"SaveImage","inputs":{"images":["6",0],"filename_prefix":"mcp_vn_"+job["id"]}}
    }
    return graph
def video_graph(job):
    return {
      "37":{"class_type":"UNETLoader","inputs":{"unet_name":"wan2.2_ti2v_5B_fp16.safetensors","weight_dtype":"default"}},
      "38":{"class_type":"CLIPLoader","inputs":{"clip_name":"umt5_xxl_fp8_e4m3fn_scaled.safetensors","type":"wan","device":"default"}},
      "39":{"class_type":"VAELoader","inputs":{"vae_name":"wan2.2_vae.safetensors"}},
      "48":{"class_type":"ModelSamplingSD3","inputs":{"model":["37",0],"shift":8}},
      "6":{"class_type":"CLIPTextEncode","inputs":{"clip":["38",0],"text":job["prompt"]}},
      "7":{"class_type":"CLIPTextEncode","inputs":{"clip":["38",0],"text":"blurry, static, flicker, motion artifacts, text, watermark, child, underage"}},
      "55":{"class_type":"Wan22ImageToVideoLatent","inputs":{"vae":["39",0],"width":512,"height":288,"length":17,"batch_size":1}},
      "3":{"class_type":"KSampler","inputs":{"model":["48",0],"positive":["6",0],"negative":["7",0],
        "latent_image":["55",0],"seed":int.from_bytes(os.urandom(6),"big"),"steps":8,
        "cfg":5,"sampler_name":"uni_pc","scheduler":"simple","denoise":1}},
      "8":{"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["39",0]}},
      "57":{"class_type":"CreateVideo","inputs":{"images":["8",0],"fps":8}},
      "58":{"class_type":"SaveVideo","inputs":{"video":["57",0],"filename_prefix":"mcp_vn_"+job["id"],"format":"mp4","codec":"h264"}}
    }
def execute(job):
    graph=video_graph(job) if job["kind"]=="video" else image_graph(job)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    result=request(COMFY,"/prompt","POST",{"prompt":graph,"client_id":"mcp-vn-worker"})
    pid=result["prompt_id"]; print("SUBMITTED",job["id"],pid,flush=True)
    timeout=time.monotonic()+(2400 if job["kind"]=="video" else 900)
    while time.monotonic()<timeout:
        time.sleep(4)
        hist=request(COMFY,"/history/"+pid)
        if pid not in hist: continue
        status=hist[pid].get("status",{})
        if status.get("status_str")!="success":
            raise RuntimeError("ComfyUI "+str(status)[:500])
        prefix="mcp_vn_"+job["id"]
        ext=".mp4" if job["kind"]=="video" else ".png"
        files=sorted(OUTPUT.glob(prefix+"_*"+ext))
        if not files:raise RuntimeError("No output file for "+job["id"])
        output=files[-1]
        payload=output.read_bytes()
        content_type="video/mp4" if ext==".mp4" else "image/png"
        if len(payload)>100_000_000:raise RuntimeError("Output too large")
        request(SERVER,"/worker/complete/"+job["id"],"POST",payload,{"Content-Type":content_type},timeout=90)
        print("COMPLETED",job["id"],output.name,len(payload),flush=True)
        return
    raise TimeoutError("Generation timed out")
def main():
    print("mcp-vn worker started",SERVER,COMFY,flush=True)
    while True:
        try:
            job=request(SERVER,"/worker/next")
            if job.get("job"):
                j=job["job"]
                try: execute(j)
                except Exception as e:
                    print("JOB ERROR",j["id"],repr(e),flush=True)
                    try:request(SERVER,"/worker/fail/"+j["id"],"POST",{"error":str(e)})
                    except Exception as report_error:print("REPORT ERROR",repr(report_error),flush=True)
            else: time.sleep(4)
        except (HTTPError,URLError,TimeoutError,KeyError) as e:
            print("CONNECTION ERROR",repr(e),flush=True);time.sleep(12)
        except Exception as e:
            print("ERROR",repr(e),flush=True);time.sleep(10)
if __name__=="__main__":
    main()
