// Artwork planner for independent VN Web (main/canonical story mode).
// Does not generate CG on every dialogue turn: a missing/new background and
// visible changed sprites are the only automatically scheduled assets.
import {enqueue,jobsForGame} from "./jobs.mjs";
import {visualFingerprint} from "./visual-state.mjs";

const clean=x=>String(x??"").trim().slice(0,180);
const backgroundPrompt=g=>{
 const s=g.scene||{};
 return [
  "Cinematic establishing background for an original fantasy visual novel.",
  "Location:",clean(s.location||"an unknown outdoor fantasy location")+".",
  "Time:",clean(s.time_of_day||"daytime")+".",
  "Weather:",clean(s.weather||"clear")+".",
  "Visual style is locked to:",clean(g.art_style)+".",
  "Match the world and existing visual style. Landscape environment.",
  "Architecture and location are the focus. No identifiable named characters.",
  "One continuous scene, no collage, no text, no watermark."
 ].join(" ");
};
const spritePrompt=(g,s)=>[
 "One adult fictional character sprite for an original fantasy visual novel.",
 "Character:",clean(s.name)+".",
 "Maintain the established character identity and stable face across frames.",
 "Outfit:",clean(s.outfit||"default")+".",
 "Pose:",clean(s.pose||"standing")+".",
 "Expression:",clean(s.emotion||"neutral")+".",
 "Narrator's current art direction:",clean(g.scene?.visual_direction||"")+".",
 "Consistent game visual style:",clean(g.art_style)+".",
 "Single character, clean neutral matte background, full-body or three-quarter portrait.",
 "No additional figures, no writing or collage."
].join(" ");
export function sceneCGPrompt(g){
 const actors=(g.scene?.sprites||[]).map(x=>x.name+": "+x.outfit+
  ", "+x.pose+", "+x.emotion).join("; ");
 const narration=(g.messages||[]).filter(x=>x.role==="narrator").at(-1)?.text||"";
 return ["Cohesive cinematic illustration of one continuous fantasy scene.",
  "Location:",clean(g.scene?.location)+".",
  "Characters and their current state:",clean(actors)+".",
  "Narrator's composition:",clean(g.scene?.visual_direction||"")+".",
  "Current story beat:",String(narration).slice(0,420)+".",
  "Use existing accepted canonical sprites and background. No extra characters.",
  "Locked art style:",clean(g.art_style)+"."].join(" ").slice(0,2000);
}
export function sceneCGRequired(g){
 const s=g?.scene||{};
 return s.auto_cg_requested===true&&!g.awaiting_narrator&&
  !!s.background_url&&!s.background_dirty&&(s.sprites||[]).length>0&&
  !(s.sprites||[]).some(p=>p.visual_dirty||!p.image_url)&&
  (!s.cg_url||s.cg_dirty||s.cg_basis!==visualFingerprint(s));
}
export function planStandaloneVisuals(g,{retry=false}={}){
 if(!g||g.local_scene?.mode==="local"||g.awaiting_narrator)
  return [];
 const s=g.scene||{};
 if(!s.background_url||s.background_dirty)
  return [{
   kind:"background",style:g.art_style,quality:"standard",
   prompt:backgroundPrompt(g),reason:"background_missing_or_changed"
  }];
 const sprites=(s.sprites||[]).filter(p=>p?.name&&
   (retry||!p.image_url||p.visual_dirty)).slice(0,4);
 if(sprites.length)return sprites.map(s=>({
  kind:"sprite",style:g.art_style,quality:"standard",
  character:s.name,outfit:s.outfit||"default",pose:s.pose||"standing",
  emotion:s.emotion||"neutral",prompt:spritePrompt(g,s),
  reason:"sprite_missing_or_changed"
 }));
 if(!retry&&sceneCGRequired(g))
  return [{kind:"scene",style:g.art_style,quality:"standard",neural_scene:true,
   prompt:sceneCGPrompt(g),reason:"narrator_material_scene_change"}];
 return [];
}
export async function scheduleStandaloneVisuals(g,{retry=false}={}){
 const wanted=planStandaloneVisuals(g,{retry}),scheduled=[],skipped=[],failed=[];
 if(!wanted.length)return {scheduled,skipped,failed,pending:false};
 const recent=await jobsForGame(g.id);
 for(const item of wanted){
  const old=recent.find(j=>j.kind===item.kind&&
    (item.kind!=="sprite"||j.character===item.character)&&
    (j.spec?.expected_location===g.scene?.location)&&
    (item.kind==="background"||item.kind==="scene"?
      j.spec?.cg_basis_snapshot===visualFingerprint(g.scene):
      j.spec?.expected_variant_key===[g.art_style,item.outfit,item.pose,item.emotion].join("|"))&&
    (j.status==="failed")&&!j.spec?.preview_only);
  if(old&&!retry){
   skipped.push({kind:item.kind,character:item.character||"",
    reason:"failed_previously",job_id:old.id});
   continue;
  }
  try{
   const j=await enqueue({...item,game_id:g.id,
     ...(retry?{force:true}:{}),
     priority:item.kind==="background"?90:item.kind==="sprite"?72:55});
   scheduled.push({kind:item.kind,character:item.character||"",
    id:j.id,status:j.status,cache_hit:!!j.cache_hit});
  }catch(e){
   failed.push({kind:item.kind,character:item.character||"",
    error:String(e.message||e).slice(0,210)});
  }
 }
 return {scheduled,skipped,failed,pending:scheduled.some(x=>
  ["queued","working"].includes(x.status))};
}
