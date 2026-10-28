// Artwork planner for independent VN Web (main/canonical story mode).
// Does not generate CG on every dialogue turn: a missing/new background and
// visible changed sprites are the only automatically scheduled assets.
import {enqueue,jobsForGame} from "./jobs.mjs";

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
 "Consistent game visual style:",clean(g.art_style)+".",
 "Single character, clean neutral matte background, full-body or three-quarter portrait.",
 "No additional figures, no writing or collage."
].join(" ");
export function planStandaloneVisuals(g){
 if(!g||g.local_scene?.mode==="local"||g.awaiting_narrator)
  return [];
 const s=g.scene||{};
 if(!s.background_url||s.background_dirty)
  return [{
   kind:"background",style:g.art_style,quality:"standard",
   prompt:backgroundPrompt(g),reason:"background_missing_or_changed"
  }];
 const sprites=(s.sprites||[]).filter(p=>p?.name&&
   (!p.image_url||p.visual_dirty)).slice(0,4);
 return sprites.map(s=>({
  kind:"sprite",style:g.art_style,quality:"standard",
  character:s.name,outfit:s.outfit||"default",pose:s.pose||"standing",
  emotion:s.emotion||"neutral",prompt:spritePrompt(g,s),
  reason:"sprite_missing_or_changed"
 }));
}
export async function scheduleStandaloneVisuals(g,{retry=false}={}){
 const wanted=planStandaloneVisuals(g),scheduled=[],skipped=[],failed=[];
 if(!wanted.length)return {scheduled,skipped,failed,pending:false};
 const recent=await jobsForGame(g.id);
 for(const item of wanted){
  const old=recent.find(j=>j.kind===item.kind&&
    (item.kind!=="sprite"||j.character===item.character)&&
    (j.spec?.expected_location===g.scene?.location)&&
    (j.status==="failed")&&!j.spec?.preview_only);
  if(old&&!retry){
   skipped.push({kind:item.kind,character:item.character||"",
    reason:"failed_previously",job_id:old.id});
   continue;
  }
  try{
   const j=await enqueue({...item,game_id:g.id,
     ...(retry?{force:true}:{}),priority:item.kind==="background"?90:72});
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
