// A scene-state contract for the private local visual-novel lane.
// Outfit, equipment, gestures, posture, location and framing are descriptive
// strings, not lists of allowed animation or clothing presets. Main game assets
// are never rewritten by this module.
const trim=(v,n=420)=>String(v??"").replace(/\s+/gu," ").trim().slice(0,n);
const namesEqual=(a,b)=>trim(a,120).toLocaleLowerCase("ru")===
  trim(b,120).toLocaleLowerCase("ru");
const asObject=x=>x&&typeof x==="object"&&!Array.isArray(x)?x:{};
const DETAIL_KEYS=["outfit","pose","expression","equipment","action"];
const CAMERA_DEFAULT="cinematic medium two-shot, natural perspective";

export function initialVisualState(game){
 const scene=asObject(game?.scene);
 const actors=(scene.sprites||[]).slice(0,5);
 return {
  schema:2,
  location:trim(scene.location,200),
  environment:trim(scene.description||game?.story?.summary,400),
  camera:actors.length===1?"cinematic medium single-character shot, natural perspective":CAMERA_DEFAULT,
  lighting:trim(scene.time_of_day||"natural ambient light",240),
  activity:"",
  characters:actors.map(x=>({
   name:trim(x.name,100),
   outfit:trim(x.outfit||"established appearance",350),
   pose:trim(x.pose||"standing",300),
   expression:trim(x.emotion||"neutral",200),
   equipment:"",
   action:""
  })),
  render:false,source:"initial"
 };
}

function legacyToState(previous,game){
 const baseline=initialVisualState(game);
 if(!previous)return baseline;
 if(previous.schema===2&&Array.isArray(previous.characters)){
  const prev=asObject(previous);
  return {
   ...baseline,
   location:trim(prev.location,200)||baseline.location,
   environment:trim(prev.environment,400)||baseline.environment,
   camera:trim(prev.camera,320)||baseline.camera,
   lighting:trim(prev.lighting,240)||baseline.lighting,
   activity:trim(prev.activity,500),
   characters:baseline.characters.map(actor=>{
    const old=asObject((prev.characters||[]).find(x=>namesEqual(x.name,actor.name)));
    return {...actor,...Object.fromEntries(DETAIL_KEYS.map(k=>[k,
      old[k]===undefined?actor[k]:trim(old[k],k==="outfit"?350:300)]))}
   }),
   render:!!prev.render,source:trim(prev.source,60)||"restored",
   last_queued:!!prev.last_queued,last_job_id:trim(prev.last_job_id,60)
  };
 }
 // Old v5.9 sessions store a fixed shot and a wardrobe preset. Convert once,
 // without replacing immutable facial identity or guessing a new outfit.
 return {...baseline,
  camera:trim(previous.shot,320)||baseline.camera,
  lighting:trim(previous.mood,240)||baseline.lighting,
  last_queued:!!previous.last_queued,
  last_job_id:trim(previous.last_job_id,60),
  source:"migrated"
 };
}

export const normalizeVisualState=legacyToState;

export const DIRECTOR_SYSTEM=[
 "You are the visual continuity director for a Russian-language interactive visual novel.",
 "Return exactly ONE JSON object, no markdown, no dialogue or explanations.",
 "Each property is unrestricted natural-language scene direction; never select from preset poses, clothing categories or equipment lists.",
 'Structure: {"location":"...","environment":"...","camera":"...","lighting":"...","activity":"...","characters":[{"name":"...","outfit":"...","pose":"...","expression":"...","equipment":"...","action":"..."}],"render":true}.',
 "All scene descriptions should be concise, visual, unambiguous English suitable for an image-generation model. Keep character names exactly as supplied.",
 "Each character's outfit, gear, weapon, posture, expression and physical action persist across turns until an actual event changes them. Include every visible character in characters.",
 "Keep clothing arrangements, equipment, posture and the current physical action consistent with the latest confirmed event. Explicitly update anything that moved or changed; do not carry forward an incompatible wardrobe description. Never invent changes not established by narration.",
 "Treat the previous visual state as authoritative continuity. If a character changes armor, sheaths a weapon, lies down, falls, stands, or changes clothes, update the relevant field precisely.",
 "Use only what was actually established by the latest NPC narration and earlier scene. A player request that an NPC rejected is NOT an accomplished change.",
 "Camera may be any shot and composition. Location and lighting may change when the narrative changes them. Do not rewrite character identities or introduce strangers.",
 "render=true when the visible moment changes substantially or a newly framed still would advance the story. Otherwise render=false.",
 "The resulting still is generated on the user's machine. You are only supplying the current visual state; you never generate the image itself."
].join("\n");

export function directorMessages({action="",narration="",previous=null,
 location="",participants=[],game=null,recent_dialogue=[]}={}){
 const current=legacyToState(previous,game||{scene:{location}});
 const cast=(participants||[]).map(p=>({
  name:trim(p.name,100),age:p.age||null
 }));
 const reference=asObject(game?.identities);
 return [
  {role:"system",content:DIRECTOR_SYSTEM},
  {role:"user",content:JSON.stringify({
   current_location:trim(location,200),
   adult_cast:cast,
   character_identity_reference:Object.keys(reference).slice(0,5),
   previous_visual:current,
   recent_local_events:(recent_dialogue||[]).slice(-8).map(e=>({
    role:e.role,text:trim(e.text,520)
   })),
   player_action:trim(action,1000),
   confirmed_npc_response:trim(narration,1800)
  })}
 ];
}

// Structural scene consistency is about physical state, not content policy.
 // Do not treat a rejected player request as an accomplished wardrobe change.
const BARE_BODY=/(?:\b(?:naked|unclothed|undressed|bare body|without clothes)\b|обнаж[её]нн?[\p{L}]*\s+тел[оауы]|полностью\s+раздет|без\s+одежды)/iu;
const FULLY_CLOTHED=/(?:\b(?:fully dressed|fully clothed|completely dressed|buttoned-up outfit)\b|полностью\s+одет)/iu;
const DECLINED_REMOVAL=/(?:отказал[а-я]*\s+разде|не\s+стал[а-я]*\s+(?:снима|разде)|\brefus(?:ed|es)\s+to\s+(?:undress|remove)|\bdid\s+not\s+(?:undress|remove))/iu;

export function visualContinuityIssues({plan,action="",narration=""}={}){
 const lines=[String(action||""),String(narration||"")];
 const context=lines.join(" ");
 const confirmed=String(narration||"");
 const exposed=BARE_BODY.test(confirmed)||
   (BARE_BODY.test(String(action||""))&&!DECLINED_REMOVAL.test(confirmed));
 if(!exposed)return [];
 const actors=Array.isArray(plan?.characters)?plan.characters:[];
 const candidates=actors.filter(c=>FULLY_CLOTHED.test(String(c.outfit||"")));
 if(!candidates.length)return [];
 return candidates.filter(c=>{
  const name=String(c.name||"");
  // When an actor is explicitly named, only flag that actor. A scene with a
  // single NPC can use pronouns without requiring specific clothing nouns.
  return !name||context.toLocaleLowerCase("ru").includes(name.toLocaleLowerCase("ru"))||
   candidates.length===1;
 }).map(c=>"Wardrobe of "+c.name+" remains fully dressed although the "+
   "latest narrated physical state describes an unclothed body.");
}

function sceneBits(state){
 return {
  location:state.location,environment:state.environment,
  camera:state.camera,lighting:state.lighting,activity:state.activity,
  characters:state.characters
 };
}

export function parseDirectorPlan(raw,{previous=null,game=null,
 narration="",action=""}={}){
 const before=legacyToState(previous,game||{});
 const text=String(raw||"").trim();
 let decoded=null;
 try{
  const first=text.indexOf("{"),last=text.lastIndexOf("}");
  if(first!==-1&&last>first&&last-first<12000)
   decoded=JSON.parse(text.slice(first,last+1));
 }catch{}
 const input=asObject(decoded);
 if(!Array.isArray(input.characters)||typeof input.render!=="boolean"){
  return {plan:{...before,render:false,source:"fallback"},
   warning:"ИИ не вернул структурированный план сцены; прежний кадр сохранён."};
 }
 const byName=input.characters.filter(x=>x&&typeof x==="object");
 const characters=before.characters.map(actor=>{
  const incoming=asObject(byName.find(x=>namesEqual(x.name,actor.name)));
  return {...actor,...Object.fromEntries(DETAIL_KEYS.map(key=>[
   key,incoming[key]===undefined?actor[key]:trim(incoming[key],key==="outfit"?350:300)
  ]))}
 });
 const state={
  schema:2,
  location:input.location===undefined?before.location:trim(input.location,200),
  environment:input.environment===undefined?before.environment:trim(input.environment,400),
  camera:input.camera===undefined?before.camera:trim(input.camera,320),
  lighting:input.lighting===undefined?before.lighting:trim(input.lighting,240),
  activity:input.activity===undefined?before.activity:trim(input.activity,500),
  characters
 };
 const changed=JSON.stringify(sceneBits(state))!==JSON.stringify(sceneBits(before));
 // Major tangible changes never disappear because the model accidentally set
 // render=false. Emotion-only prose can remain a text turn when requested.
 const materialChange=state.location!==before.location||
  state.environment!==before.environment||
  state.characters.some((actor,i)=>{
   const old=before.characters[i];
   return ["outfit","pose","equipment","action"].some(k=>actor[k]!==old[k]);
  });
 return {
  plan:{...state,render:(input.render||materialChange)&&
    (changed||!before.last_queued),source:"ai_director"},
  warning:""
 };
}

// Backwards compatibility for older responses that included a final control
// tag. The story is always stored without internal metadata.
export function extractLocalVisual(raw){
 const rawText=String(raw??"");
 return {narration:rawText.replace(/\s*\[\[VN_VISUAL[^\]\n]*\]\]\s*$/iu,"").trim(),
  plan:null};
}
