// Authoritative, size-bounded story state for a single AI-narrator turn.
// Never includes asset URLs, previous image jobs, face crops or undo snapshots.
// Full state remains available through get_game for interactive UI/debugging.
import {queryMemory} from "./story-memory.mjs";

const clip=(v,n=500)=>String(v??"").trim().replace(/\s+/gu," ").slice(0,n);
function profile(description=""){
 const original=String(description||"");
 const extract=(start,ends,limit)=>{
  const begin=original.search(start);if(begin<0)return "";
  let txt=original.slice(begin).replace(start,"").trim();
  for(const end of ends){
   const p=txt.search(end);if(p>=0)txt=txt.slice(0,p);
  }
  return clip(txt,limit);
 };
 return {
  appearance:extract(/(?:Внешность|Appearance)\s*:/iu,[/\n\s*(?:Характер|Манера речи|Личность|Предыстория|Character|Personality)\s*:/iu],520),
  personality:extract(/(?:Характер|Personality)\s*:/iu,[/\n\s*(?:Манера речи|Личность|Нравится|Не нравится|Сильные стороны|Предыстория|Speaking)\s*:/iu],360),
  speaking:extract(/(?:Манера речи|Speaking style)\s*:/iu,[/\n\s*(?:Личность|Нравится|Предыстория|Отношение)\s*:/iu],260)
 };
}
const npcCard=c=>({
 name:clip(c.name,80),age:Number.isFinite(c.age)?c.age:null,
 description:clip(c.description,280)
});
const recent=m=>({
 role:m.role==="player"?"player":"narrator",
 speaker:clip(m.speaker,70),text:clip(m.text,620)
});
export function makeNarrationPacket(game,{maxChars=11200}={}){
 const action=(game.messages||[]).filter(x=>x.role==="player").at(-1);
 const memory=queryMemory(game,action?.text||"");
 const hero=profile(game.hero?.description);
 const activeActors=(game.scene?.sprites||[]).slice(0,8).map(s=>({
  name:clip(s.name,80),outfit:clip(s.outfit,100),pose:clip(s.pose,80),
  emotion:clip(s.emotion,70),needs_visual_refresh:s.visual_dirty===true
 }));
 const packet={
  protocol:"mcp-vn/narrator-packet-v1",game_id:game.id,expected_version:game.version,
  local_scene_mode:game.local_scene?.mode||"main",
  pending_narration:!!game.awaiting_narrator,
  pending_action:{id:action?.id||"",speaker:clip(action?.speaker,80),text:clip(action?.text,1900)},
  story:{title:clip(game.title,120),summary:clip(game.story?.summary,330),
    lore:clip(game.story?.lore,450)},
  protagonist:{name:clip(game.hero?.name,80),...hero},
  characters:(game.story?.characters||[]).slice(0,12).map(npcCard),
  scene:{location:clip(game.scene?.location,160),
    time_of_day:clip(game.scene?.time_of_day,60),
    weather:clip(game.scene?.weather,60),
    visual_style:game.art_style,visible:activeActors},
  rules:{mode:game.rules?.mode||"narrative",
    stats:game.rules?.mode==="adventure"?game.rules?.stats:undefined,
    recent_check:game.rules?.mode==="adventure"?game.rules?.history?.at(-1):undefined},
  flags:Object.fromEntries(Object.entries(game.flags||{}).slice(-80)),
  relationships:game.relationships||{},inventory:(game.inventory||[]).slice(-35),
  memory:{
    established_facts:memory.facts.slice(0,10).map(f=>({
      subject:clip(f.subject,90),key:clip(f.key,80),value:clip(f.value,370),scope:f.scope})),
    notes:memory.notes.slice(0,5).map(n=>({subject:clip(n.subject,90),text:clip(n.text,220)})),
    quests:memory.quests.slice(0,5).map(q=>({
      title:clip(q.title,140),status:q.status,objective:clip(q.objective,300)})),
    chapters:memory.chapters.slice(-2).map(c=>({
      number:c.number||c.index,status:c.status,
      synopsis:clip(c.synopsis,630),
      decisions:(c.player_decisions||[]).slice(-4).map(x=>clip(x,120))})),
    recent_events:memory.recent_events.slice(-5).map(e=>({
      kind:e.kind,text:clip(e.text,230)}))
  },
  recent_dialogue:(game.messages||[]).slice(-10).map(recent)
 };
 // Preserve current action, world facts and the character's stable identity first.
 // Only prune history, which is already represented in episodic memory.
 const size=()=>JSON.stringify(packet).length;
 const cap=Math.max(5000,Math.min(18000,Number(maxChars)||11200));
 while(size()>cap&&packet.recent_dialogue.length>5)packet.recent_dialogue.shift();
 while(size()>cap&&packet.memory.recent_events.length>2)packet.memory.recent_events.shift();
 while(size()>cap&&packet.memory.chapters.length>1)packet.memory.chapters.shift();
 while(size()>cap&&packet.memory.established_facts.length>4)packet.memory.established_facts.pop();
 packet.meta={context_characters:size(),history_available_through:"get_game_context(detail=full)"};
 return packet;
}
