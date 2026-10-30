#!/usr/bin/env python3
"""Non-generating validation of v6.3 graphs on the actual ROCm worker Python."""
import os,sys
from pathlib import Path
os.environ.setdefault("VN_WORKER_TOKEN","test-only-graph-token")
os.environ["VN_POSE_CONTROL"]="0"
os.environ["VN_IPADAPTER"]="0"
os.environ.setdefault("VN_LOCAL_CG_CHECKPOINT","CyberRealisticPony_V18.0_F16.safetensors")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from worker import image_graph,STYLES

styles={
    "realistic":("CheckpointLoaderSimple","CyberRealisticPony_V18.0_F16.safetensors"),
    "semireal":("CheckpointLoaderSimple","CyberRealisticPony_V18.0_F16.safetensors"),
    "poster":("CheckpointLoaderSimple","CyberRealisticPony_V18.0_F16.safetensors"),
    "anime":("CheckpointLoaderSimple","waiIllustriousSDXL_v170.safetensors"),
    "animation":("UNETLoader","BASNSFWBetterAnimeStyleForNSFWHentai_baseV10.safetensors"),
}
for name,(node_type,model) in styles.items():
    for kind in ("background","sprite","local_cg"):
        spec={"resolution":[768,768],"quality":"standard","variant":{
            "pose":"standing","outfit":"default","emotion":"neutral"},
            "location":"Medieval town square",
            "environment":{"positive":["stone streets","wooden market stalls"],"negative":["forest"],"id":"outdoor_market_square"},
            "characters":[],"visible_count":0,"local_fresh_composition":True}
        job={"style":name,"kind":kind,"prompt":"A peaceful outdoor medieval market square under bright daylight","attempts":1,
             "id":"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee","character":"Fictional adult","spec":spec}
        graph,background=image_graph(job)
        assert background is None
        assert graph["1"]["class_type"]==node_type,(name,kind)
        key="ckpt_name" if node_type=="CheckpointLoaderSimple" else "unet_name"
        assert graph["1"]["inputs"][key]==model,(name,kind,graph["1"])
        assert graph["7"]["class_type"]=="SaveImage"
        if name=="animation":
            assert graph["13"]["class_type"]=="CLIPLoader"
            assert graph["14"]["class_type"]=="VAELoader"
            assert graph["5"]["inputs"]["steps"]==8
            assert graph["6"]["inputs"]["vae"]==["14",0]
            assert graph["5"]["inputs"]["sampler_name"]=="euler"
            assert not any("IPAdapter" in v["class_type"] or "ControlNet" in v["class_type"] for v in graph.values())
        else:
            assert graph["8"]["class_type"]=="CLIPSetLastLayer"
            assert graph["6"]["inputs"]["vae"]==["1",2]
        print("GRAPH_OK",name,kind,len(graph),flush=True)
print("ALL_15_STYLE_GRAPHS_PASS",flush=True)
