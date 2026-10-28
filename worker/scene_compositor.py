#!/usr/bin/env python3
"""Deterministic cinematic composition from approved sprites and the original scene.
Identity, character count and background geometry cannot drift.
"""
import math
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageStat

TARGET=(1216,704)
def compose(job, fetch):
 spec=job.get("spec") or {}
 bg_name=spec.get("background_asset")
 if not bg_name:raise ValueError("Missing canonical background")
 backdrop=fetch(bg_name)
 if backdrop is None:raise ValueError("Cannot load canonical background")
 img=ImageOps.fit(backdrop.convert("RGB"),TARGET,method=Image.Resampling.LANCZOS).convert("RGBA")
 original=img.copy()
 chars=spec.get("characters") or []
 if not chars or len(chars)>5:raise ValueError("CG requires 1-5 visible characters")
 if any(not c.get("sprite_alpha") or not c.get("sprite_asset") for c in chars):
  raise ValueError("CG requires accepted alpha sprite for every visible character")
 n=len(chars)
 xCenters={1:[.50],2:[.31,.69],3:[.19,.50,.81],4:[.135,.37,.63,.865],5:[.10,.29,.50,.71,.90]}[n]
 floor_y=.955
 personHeight={1:.88,2:.80,3:.70,4:.63,5:.57}[n]
 local=job.get("kind")=="local_cg"
 local_assets=spec.get("local_sprite_assets") or []
 if local:
  if len(local_assets)!=n:raise ValueError("Local CG needs validated alternative sprites for all visible characters")
  shot=spec.get("local_shot","face_to_face")
  layouts={
   "face_to_face":([.34,.66],.84,.955),
   "beside":([.36,.64],.68,.90),
   "embrace":([.43,.57],.82,.96),
   "walking":([.34,.66],.81,.95),
   "closeup":([.33,.67],1.03,1.16)
  }
  if n==2 and shot in layouts:
   xCenters,personHeight,floor_y=layouts[shot]
  elif n>5:
   raise ValueError("Too many local characters")
 # Foreground depth changes very slightly with x to avoid visual uniformity.
 for index,person in enumerate(chars):
  source_asset=local_assets[index] if local else person["sprite_asset"]
  src=fetch(source_asset)
  if src is None:raise ValueError("Cannot retrieve "+person["name"]+" sprite")
  src=src.convert("RGBA")
  alpha=src.getchannel("A")
  bbox=alpha.point(lambda v:255 if v>18 else 0).getbbox()
  if not bbox:raise ValueError("Empty sprite alpha: "+person["name"])
  src=src.crop(bbox)
  scale=TARGET[1]*personHeight/src.height
  size=(max(1,int(src.width*scale)),max(1,int(src.height*scale)))
  actor=src.resize(size,Image.Resampling.LANCZOS)
  px=int(TARGET[0]*xCenters[index]-actor.width*.5)
  bottom=int(TARGET[1]*floor_y)
  py=bottom-actor.height
  # Subtle shadow on ground and behind the actor. Never redraw identity pixels.
  shadow=Image.new("RGBA",TARGET,(0,0,0,0))
  shadow_alpha=actor.getchannel("A").point(lambda v:int(v*.20))
  shadow_body=Image.new("RGBA",actor.size,(0,0,0,0))
  shadow_body.putalpha(shadow_alpha)
  shadow.alpha_composite(shadow_body,(px+13,py+9))
  shadow=shadow.filter(ImageFilter.GaussianBlur(12))
  img=Image.alpha_composite(img,shadow)
  ground=Image.new("RGBA",TARGET,(0,0,0,0))
  ellipse=ImageDraw.Draw(ground,"RGBA")
  radius=max(25,int(actor.width*.48))
  ellipse.ellipse((px+actor.width*.5-radius,bottom-13,
                   px+actor.width*.5+radius,bottom+12),fill=(0,0,0,85))
  ground=ground.filter(ImageFilter.GaussianBlur(11))
  img=Image.alpha_composite(img,ground)
  img.alpha_composite(actor,(px,py))
 return img.convert("RGB"),{"characters_composited":n,
  "composition":"anchored_local_composite" if local else "anchored",
  "shot":spec.get("local_shot","") if local else ""}
