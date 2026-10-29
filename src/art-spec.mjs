import {environmentFor} from "./environment.mjs";
import {engineSnapshot} from "./engine-policy.mjs";
import {variantKey,visualFingerprint,sceneIntentFingerprint} from "./visual-state.mjs";
import {requireStyle} from "./art-style.mjs";
const permittedStyle=new Set(["anime","animation","semireal","realistic","poster"]);
const qModes=new Set(["fast","standard","cinematic"]);
const compact=(str,n=1000)=>String(str||"").trim().replace(/\s+/g," ").slice(0,n);
export const assetName=url=>{
 if(typeof url!=="string")return "";
 try{const u=new URL(url);const name=u.pathname.split("/").at(-1)||"";
  return /^[a-f0-9-]{36}\.(png|jpg|webp)$/i.test(name)?name:"";
 }catch{return ""}
};
export function appearance(text){
 const t=String(text||"");
 const m=t.match(/(?:Внешность|Appearance)\s*:\s*([\s\S]*?)(?:\n\s*(?:Характер|Character|Манера речи|Личность)\s*:|$)/i);
 return compact(m?m[1]:t,1100);
}
export function characterDescription(g,name){
 const n=compact(name,100);
 if(n.toLowerCase()===String(g.hero?.name||"").toLowerCase())return appearance(g.hero?.description);
 const item=(g.story?.characters||[]).find(c=>String(c.name||"").toLowerCase()===n.toLowerCase());
 return compact(item?.description||"",1100);
}
export function identityFor(g,name){
 const entries=g.identities||{};
 return entries[name]||Object.values(entries).find(x=>String(x.name||"").toLowerCase()===String(name||"").toLowerCase())||null;
}
function currentSprite(g,name){
 return(g.scene?.sprites||[]).find(s=>s.name===name);
}
export function artSnapshot(g,{kind,style,character,prompt,quality="standard",
 outfit,pose,emotion,force=false,preview_only=false,library_only=false,
 target_location="",target_time_of_day="",target_weather="",
 local_shot="",local_variant_jobs=[],
 local_visual_state=null,local_basis_asset="",local_basis_job_id="",
 local_basis_verified=false,local_fresh_composition=false,
 video_start_asset="",video_source_verified=false,neural_scene=false,narrator_prompt=false}){
 requireStyle(style);
 if(style!==g.art_style)throw Error("Art style locked to "+g.art_style+" for this game");
 if(!qModes.has(quality))throw Error("Invalid quality preset");
 if(preview_only&&!["sprite","background","scene","local_cg","video"].includes(kind))
  throw Error("Preview kind not supported");
 if(kind==="local_cg"&&!preview_only)
  throw Error("Local CG must always be a noncanonical preview");
 if(video_start_asset&&!preview_only)
  throw Error("Local story video must remain a private preview");
 if(video_start_asset&&video_source_verified!==true)
  throw Error("Video start frame needs independent scene verification");
 if(local_basis_asset&&local_basis_verified!==true)
  throw Error("Previous CG is not visually verified and cannot serve as seed");
 if(kind==="local_cg"&&g.local_scene?.mode!=="local")
  throw Error("Local CG requires an active local episode");
 if(library_only&&(!["sprite","background"].includes(kind)||preview_only))
  throw Error("Library warmup supports sprite/background only, not previews");
 const scene=g.scene||{},sprites=Array.isArray(scene.sprites)?scene.sprites:[];
 if(target_location&&(!library_only||kind!=="background"))
   throw Error("Target location is only allowed for cached background pre-generation");
 const localLocation=kind==="local_cg"?
  compact(local_visual_state?.location,180):"";
 const location=compact(localLocation||target_location||scene.location,180);
 const environment=environmentFor(localLocation?{location}:target_location?{location}:scene);
 const identity=identityFor(g,character);
 const sprite=currentSprite(g,character);
 const characters=sprites.map(s=>{
  const canonical=identityFor(g,s.name);
  return {name:compact(s.name,100),appearance:characterDescription(g,s.name),
   sprite_asset:assetName(s.image_url),sprite_alpha:s.transparent===true,
   // Optional storyteller-specified normalized foreground region [x,y,w,h].
   // Omit when unknown; worker uses conservative equal-column group framing.
   actor_region:Array.isArray(s.actor_region)&&s.actor_region.length===4&&
     s.actor_region.every(v=>typeof v==="number"&&Number.isFinite(v))?
     s.actor_region:null,
   visual_dirty:s.visual_dirty===true,
   desired_variant_key:s.desired_variant_key||variantKey(s),
   rendered_variant_key:s.rendered_variant_key||"",
   rendered_background_asset:s.rendered_background_asset||"",
   anchor_asset:assetName(canonical?.base_sprite_url),
   anchor_face_asset:assetName(canonical?.face_url),
   emotion:compact(s.emotion||"neutral",60),outfit:compact(s.outfit||"default",80),
   pose:compact(s.pose||"standing",280)};
 });
 const available=characters.filter(c=>c.sprite_asset&&c.sprite_alpha&&!c.visual_dirty);
 const face=assetName(identity?.face_url);
 const base=assetName(identity?.base_sprite_url);
 const variant={outfit:compact(outfit||sprite?.outfit||"default",320),
   pose:compact(pose||sprite?.pose||"standing",280),
   emotion:compact(emotion||sprite?.emotion||"neutral",120)};
 const spec={
  spec_version:10,engine:engineSnapshot(),story_id:g.story_id||"",
  kind,style,quality,preview_only:!!preview_only,
  narrator_prompt:narrator_prompt===true,
  local_session_id:(kind==="local_cg"||video_start_asset)?
    (g.local_scene?.session_id||""):"",
  local_shot:kind==="local_cg"?compact(local_shot,48):"",
  local_variant_jobs:kind==="local_cg"?(Array.isArray(local_variant_jobs)?local_variant_jobs.slice(0,5):[]):[],
  local_visual_state:(kind==="local_cg"||video_start_asset)&&
    local_visual_state&&typeof local_visual_state==="object"?
    JSON.parse(JSON.stringify(local_visual_state)):null,
  local_basis_asset:assetName(local_basis_asset),
  local_basis_job_id:compact(local_basis_job_id,50),
  local_basis_verified:local_basis_verified===true,
  local_fresh_composition:kind==="local_cg"&&local_fresh_composition===true,
  video_start_asset:assetName(video_start_asset),
  video_source_verified:video_source_verified===true,
  library_only:!!library_only,location,environment,
  target_time_of_day:compact(target_time_of_day,40),target_weather:compact(target_weather,40),
  world:compact(g.story?.summary,300),lore:compact(g.story?.lore,300),
  prompt:compact(prompt,4000),character:compact(character,100),
  appearance:kind==="sprite"?characterDescription(g,character):"",
  characters,visible_count:characters.length,ready_count:available.length,
  background_asset:assetName(scene.background_url),background_style:scene.background_style||"",
  anchor_asset:base,face_asset:face,anchor_style:identity?.base_style||"",
  previous_sprite_asset:assetName(sprite?.image_url),
  variant,expected_variant_key:variantKey({art_style:style,...variant}),
  cg_basis_snapshot:kind==="scene"&&neural_scene?sceneIntentFingerprint(scene):visualFingerprint(scene),
  force:!!force,expected_location:kind==="local_cg"?
    compact(scene.location,180):location,
  output:kind==="sprite"?"rgba_sprite":kind==="scene"?"cg":kind,
  composition:kind==="local_cg"?"neural_story":
    (kind==="video"&&video_start_asset)?"story_video":
    kind==="scene"?(neural_scene?"neural_story":"anchored_composite"):kind==="sprite"?"transparent_layer":"standalone",
  // CPU scene previews use the compositor's fixed native canvas, but never
  // attach to the canonical game CG. Background/sprite previews are smaller.
  resolution:preview_only?(kind==="sprite"?[640,960]:
    kind==="local_cg"?[896,1152]:kind==="scene"?[1216,704]:[896,512]):
    kind==="sprite"?[832,1216]:kind==="video"?[512,288]:[1216,704],
  required_checks:kind==="sprite"?["png_dimensions","nonempty_alpha","foreground_bounds","single_character"]:
    ["file_signature","dimensions","scene_semantics"],
  max_attempts:quality==="fast"?2:3
 };
 return spec;
}
export function currentSceneMatches(g,spec){
 if(!spec)return true;
 if(spec.style!==g.art_style)return false;
 if(spec.local_session_id&&(g.local_scene?.mode!=="local"||
    g.local_scene?.session_id!==spec.local_session_id))return false;
 if(spec.kind==="background"&&spec.library_only)return true;
 if(String(g.scene?.location||"")!==String(spec.expected_location||""))return false;
 if(["sprite","scene","local_cg"].includes(spec.kind)){
  if(assetName(g.scene?.background_url)!==String(spec.background_asset||""))return false;
  if(spec.kind==="sprite"&&!spec.library_only&&!spec.preview_only){
   const current=(g.scene?.sprites||[]).find(s=>s.name===spec.character);
   if(current){
    const requested=spec.variant||{};
    if(String(current.outfit||"default")!==String(requested.outfit||"default")||
       String(current.pose||"standing")!==String(requested.pose||"standing")||
       String(current.emotion||"neutral")!==String(requested.emotion||"neutral"))
      return false;
   }
  }
  if(spec.kind==="scene"){
   const neural=spec.composition==="neural_story";
   if(!neural&&g.scene?.sprites?.some(s=>s.visual_dirty))return false;
   if((neural?sceneIntentFingerprint(g.scene):visualFingerprint(g.scene))!==
      spec.cg_basis_snapshot)return false;
   const now=g.scene?.sprites||[];
   if(now.length!==spec.characters.length)return false;
   for(let i=0;i<now.length;i++){
    if(now[i].name!==spec.characters[i].name)return false;
    if(!neural&&assetName(now[i].image_url)!==spec.characters[i].sprite_asset)
     return false;
   }
  }
  // A separately rendered local CG never modifies the canonical image.
  // It may use unchanged canonical face anchors even when the main-story
  // sprite outfit is intentionally stale during private dialogue.
 }
 return true;
}
