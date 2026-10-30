#!/usr/bin/env python3
"""Private Z-Image native model A/B: text adherence on real ComfyUI.

No game/server calls. Uses precisely the official Z Image text2img graph
adapted to existing installed model files. Writes outside canonical game data.
"""
import argparse,json,time,uuid,urllib.request,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from zimage_backend import create_graph,prepare_game_canvas

COMFY='http://127.0.0.1:8188'
MODELS={
 'unet':'z_image_turbo_bf16_fp8_scaled_1.safetensors',
 'clip':'qwen_3_4b_fp4_mixed.safetensors',
 'vae':'ae.safetensors',
}
PROMPTS={
 'map':"""A single coherent cinematic photograph in a medieval European market square under morning sunlight. In the foreground, exactly one adult female adventurer with shoulder-length auburn brown hair wearing a CLOSED BLUE TRAVEL JACKET with a belt and trousers. She is STUDYING A FOLDED PAPER MAP, holding it OPEN in BOTH hands and looking DOWN at its printed paths, NOT holding food or a basket. The map is clearly visible with lines and trails on paper. Behind her: timber frame buildings, fruit stalls and a distant clock tower. Medium wide landscape camera shot, natural anatomy, story action unmistakable, no photo equipment.""",
 'arch':"""One cinematic photo, same adult auburn-haired female adventurer wearing the same CLOSED BLUE TRAVEL JACKET, belt and trousers. She is WALKING THROUGH AND UNDER A LARGE STONE ARCHWAY of the medieval market gate. The central STONE ARCH spans overhead, curved stone masonry surrounds the character. She carries a rolled paper map in her LEFT hand, moving away from the marketplace stalls seen in the background. Wide 3/4 shot, no photo equipment, one subject, detailed architecture, natural daylight.""",
 'wall':"""Single coherent cinematic photograph of one adult brown-haired female explorer in a BLUE JACKET AND DARK TROUSERS, from behind in a 3/4 rear view at a medieval market square. She is STANDING WITH STRAIGHT LEGS, bent forward at the hips, BOTH PALMS FLAT AGAINST a VERTICAL STONE WALL supporting her weight. BOTH hands distinctly touch the STONE WALL at shoulder height. Feet rest on cobblestone ground, body upright-supported, NOT seated or kneeling. Camera from behind looking along the wall; no photographer or camera equipment in picture.""",
 'sprite':"""One isolated full-body character sprite for a fantasy roleplaying game. A single adult female explorer with shoulder-length auburn brown hair and symmetrical face stands UPRIGHT in a neutral symmetrical A-pose, both FEET ON GROUND and in the frame. She is wearing a CLOSED DEEP BLUE TRAVEL JACKET, a BELT, FULL LENGTH DARK TROUSERS and practical brown leather boots; clothing fully covers torso and legs. Full-length centered straight-on view. A plain seamless neutral mid-gray background, no ground props, no camera equipment, no photography tripod, no scenery, no text, no additional people."""
}
def req(path,method='GET',data=None,timeout=20):
    payload=None if data is None else json.dumps(data).encode('utf-8')
    request=urllib.request.Request(COMFY+path,data=payload,method=method,headers={'Content-Type':'application/json'} if payload else {})
    with urllib.request.urlopen(request,timeout=timeout) as response:return json.load(response)
def graph(prompt,seed,prefix,width,height):
    return create_graph(prompt,seed=seed,prefix=prefix,width=width,height=height,
                        private_unanchored=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--only',choices=[*PROMPTS,'all'],default='all');p.add_argument('--seed',type=int,default=2026103001)
    p.add_argument('--compact',action='store_true',help='Constrain native Z-Image dimensions to at most 1024 pixels')
    p.add_argument('--native',action='store_true',help='Resize accepted PNG to game size and extract sprite alpha (experimental)')
    args=p.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True,mode=0o700)
    names=list(PROMPTS) if args.only=='all' else [args.only]
    results=[]
    alpha_session=None
    for n in names:
      start=time.monotonic();wid,hei=((704,1024) if n=='sprite' else (1024,592)) if args.compact else ((832,1216) if n=='sprite' else (1216,704))
      summary={'kind':n,'seed':args.seed,'model':MODELS,'status':'unknown'}
      try:
        prefix='vn_zimage_probe_'+n+'_'+str(uuid.uuid4())[:8]
        prompt=PROMPTS[n];job={'prompt':graph(prompt,args.seed,prefix,wid,hei),'client_id':str(uuid.uuid4())}
        q=req('/prompt','POST',job);summary['prompt_id']=q.get('prompt_id');summary['errors']=q.get('node_errors')
        if not q.get('prompt_id'):raise RuntimeError('ComfyUI rejected graph: '+str(q)[:900])
        deadline=time.monotonic()+420
        while time.monotonic()<deadline:
          time.sleep(2)
          history=req('/history/'+q['prompt_id'])
          if q['prompt_id'] not in history:continue
          hist=history[q['prompt_id']]
          if hist.get('status',{}).get('status_str')!='success':
            raise RuntimeError('ComfyUI graph failed: '+str(hist.get('status'))[-1300:])
          image=(hist.get('outputs',{}).get('10',{}).get('images') or [])[0]
          source=(Path.home()/'.local/share/mcp-vn-comfy/output'/image.get('subfolder','')/image['filename']).resolve()
          if not source.is_file():raise RuntimeError('output missing: '+str(source))
          dest=out/(n+'.png');shutil.copy2(source,dest);dest.chmod(0o600)
          summary['output']=str(dest);summary['status']='ok'
          if args.native:
            raw=dest.read_bytes()
            if n=='sprite':
                from rembg import new_session,remove
                if alpha_session is None:
                    alpha_session=new_session('isnet-general-use',providers=['CPUExecutionProvider'])
                cutout=lambda im:remove(im,session=alpha_session,alpha_matting=False).convert('RGBA')
            else:
                cutout=None
            from PIL import Image
            native_bytes=prepare_game_canvas(raw,n,sprite_cutout=cutout)
            native_path=out/(n+'.native.png')
            native_path.write_bytes(native_bytes)
            native_path.chmod(0o600)
            with Image.open(native_path) as native:
                summary['native_output']=str(native_path)
                summary['native_size']=native.size
                if n=='sprite':
                    a=native.getchannel('A')
                    summary['transparent_fraction']=round(sum(a.histogram()[:24])/(a.width*a.height),4)
                    summary['foreground_bbox']=a.point(lambda v:255 if v>80 else 0).getbbox()
          break
        else:raise TimeoutError('generation timeout')
      except Exception as error:summary['status']='failed';summary['error']=str(error)[:1500]
      summary['seconds']=round(time.monotonic()-start,2);results.append(summary)
      (out/(n+'.json')).write_text(json.dumps(summary,indent=2))
      print(json.dumps(summary),flush=True)
    print('MODEL_PROBE_FINISHED',flush=True)
if __name__=='__main__':main()
