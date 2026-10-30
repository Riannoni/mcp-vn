"""Experimental Z-Image-Turbo text-to-image graph. NEVER an SDXL graph.

Pure, isolated and identity-safe. No production dispatcher invokes this yet.
A character with an established canonical anchor MUST NOT silently lose it.
Only the explicitly unanchored, private GPU canary may opt in to T2I.
"""
from __future__ import annotations

from io import BytesIO
from PIL import Image

DEFAULT_MODEL='z_image_turbo_bf16_fp8_scaled_1.safetensors'
DEFAULT_ENCODER='qwen_3_4b_fp4_mixed.safetensors'
DEFAULT_VAE='ae.safetensors'
CG_CANVAS=(1024,592)
SPRITE_CANVAS=(704,1024)
GAME_CG_CANVAS=(1216,704)
GAME_SPRITE_CANVAS=(832,1216)


def create_graph(prompt, *, seed, prefix, width, height, private_unanchored=False,
                 canonical_face_asset=None, model=DEFAULT_MODEL,
                 encoder=DEFAULT_ENCODER, vae=DEFAULT_VAE):
    """Return a pinned Comfy API graph, or fail before GPU inference.

    Identity-conditioned Z-Image requires a *native*, measured adapter or
    character LoRA and is not implemented. SDXL Face IPAdapter does NOT work.
    The sole supported mode is a private unanchored evaluation image.
    """
    if not private_unanchored:
        raise ValueError('Z-Image not authorized for canonical/game rendering')
    if canonical_face_asset:
        raise ValueError('Z-Image private T2I cannot preserve canonical character identity')
    if not isinstance(seed,int) or isinstance(seed,bool) or not 0<=seed<2**48:
        raise ValueError('Invalid Z-Image seed')
    if any(not isinstance(v,int) or isinstance(v,bool) or v<256 or v>1024 or v%16 for v in (width,height)):
        raise ValueError('Z-Image canvas must be 256..1024 and divisible by 16')
    if not isinstance(prompt,str) or not 10<=len(prompt)<=5000 or '\x00' in prompt:
        raise ValueError('Invalid Z-Image prompt')
    if not isinstance(prefix,str) or not prefix.startswith('vn_zimage_probe_') or not prefix.replace('_','').replace('-','').isalnum():
        raise ValueError('Only isolated Z-Image probe output prefixes are allowed')
    if (model,encoder,vae)!=(DEFAULT_MODEL,DEFAULT_ENCODER,DEFAULT_VAE):
        raise ValueError('Unmeasured model combination: pin tested Z-Image FP8 stack')
    return {
        '1':{'class_type':'UNETLoader','inputs':{'unet_name':model,'weight_dtype':'default'}},
        '2':{'class_type':'CLIPLoader','inputs':{'clip_name':encoder,'type':'lumina2','device':'default'}},
        '3':{'class_type':'VAELoader','inputs':{'vae_name':vae}},
        '4':{'class_type':'CLIPTextEncode','inputs':{'clip':['2',0],'text':prompt}},
        '5':{'class_type':'ConditioningZeroOut','inputs':{'conditioning':['4',0]}},
        '6':{'class_type':'ModelSamplingAuraFlow','inputs':{'model':['1',0],'shift':3}},
        '7':{'class_type':'EmptySD3LatentImage','inputs':{'width':width,'height':height,'batch_size':1}},
        '8':{'class_type':'KSampler','inputs':{'model':['6',0],'positive':['4',0],'negative':['5',0],
               'latent_image':['7',0],'seed':seed,'steps':8,'cfg':1.0,
               'sampler_name':'res_multistep','scheduler':'simple','denoise':1.0}},
        '9':{'class_type':'VAEDecode','inputs':{'samples':['8',0],'vae':['3',0]}},
        '10':{'class_type':'SaveImage','inputs':{'images':['9',0],'filename_prefix':prefix}}
    }


def prepare_game_canvas(raw,kind,*,sprite_cutout=None):
    """Read-only candidate raster conversion. Never claims QA success.

    Character RGBA requires explicit background removal, which must be
    separately QA-tested for alpha, limbs and clothing preservation.
    """
    if kind not in ('sprite','map','arch','wall','cg'):
        raise ValueError('Unsupported canary image role')
    with Image.open(BytesIO(raw)) as image:
        image.load()
        rgb=image.convert('RGB')
    target=GAME_SPRITE_CANVAS if kind=='sprite' else GAME_CG_CANVAS
    resized=rgb.resize(target,Image.Resampling.LANCZOS)
    if kind=='sprite':
        if not callable(sprite_cutout):
            raise ValueError('Sprite alpha removal required; RGB is never an accepted sprite')
        resized=sprite_cutout(resized)
        if resized.mode!='RGBA' or resized.size!=target:
            raise ValueError('Sprite cutout must return native-size RGBA')
        alpha=resized.getchannel('A')
        if sum(alpha.histogram()[:24])/(alpha.width*alpha.height)<.12:
            raise ValueError('Sprite matte has insufficient transparent background')
        if alpha.point(lambda value:255 if value>80 else 0).getbbox() is None:
            raise ValueError('Empty sprite subject')
    out=BytesIO()
    resized.save(out,format='PNG')
    return out.getvalue()
