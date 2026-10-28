// Deterministic local visual-routing policy for the on-device VN.
// One turn schedules ONE visual lane: reuse, transparent sprite(s), or full CG.
// The director describes what happened; it must not independently decide GPU work.
import {createHash} from "node:crypto";

const flat=x=>String(x??"").replace(/\s+/gu," ").trim().toLocaleLowerCase("ru");
const materialAction=/(?:обня|поцелов|прижа|схват|поднял[аи]?|подхват|повал|легл[аи]?|ложит|улож|раздел|раздев|снял[аи]?|опустил[аи]?с[ья]|оттолк|толкнул|удар|сража|прыж|упал|прикас|касал|трога|соприкос|взял[аи]? за руку|сел[аи]? на колени|embrac|kiss|hug|grabb|lift|lie down|lying down|leaning against|touching|pressing|undress|remove clothing|fight|fall|kneel)/iu;
const subtleAction=/(?:улыб|взгляд|вздох|нахмур|кивнул|повернул[аи]? голов|прошептал|сказал|говор|смеял|морг|look|smil|nod|blink|frown|glanc|spea|said|whisper|laugh|sigh|breath)/iu;
const cameraRequest=/(?:ракурс|кадр|камер|взгляд сверху|вид снизу|портрет|приблиз|крупн[ыйм]|shot|camera|framing|close.?up|angle|zoom)/iu;
const smallPose=/(?:смотрит|улыб|нахмур|кив|поворот головы|взгляд|look|smil|frown|tilt head|glance|nod|blink|neutral|standing|стоит)/iu;
const keysPhysical=["outfit","equipment","pose","action"];
const normalActor=c=>({
 name:flat(c?.name),outfit:flat(c?.outfit),equipment:flat(c?.equipment),
 pose:flat(c?.pose),action:flat(c?.action)
});
export function visualSignature(state,{style="",includeExpression=false}={}){
 const v=state||{};
 const actors=(v.characters||[]).map(c=>({
  ...normalActor(c),...(includeExpression?{expression:flat(c.expression)}:{})
 }));
 const data=[flat(style),flat(v.location),flat(v.environment),
   flat(v.camera),flat(v.lighting),flat(v.activity),actors];
 return createHash("sha256").update(JSON.stringify(data)).digest("hex");
}
export function spriteSignature(character,location="",style=""){
 return createHash("sha256").update(JSON.stringify([
  flat(style),flat(location),flat(character?.name),flat(character?.outfit),
  flat(character?.pose),flat(character?.expression),flat(character?.equipment)
 ])).digest("hex");
}
function actorsByName(state){
 return new Map((state?.characters||[]).map(c=>[flat(c.name),c]));
}
function changes(previous,next){
 const prior=actorsByName(previous),current=actorsByName(next);
 const names=new Set([...prior.keys(),...current.keys()]);
 const delta=[];
 for(const name of names){
  const a=prior.get(name),b=current.get(name);
  if(!a||!b){delta.push({name,fields:["cast"]});continue}
  const fields=[...keysPhysical,"expression"].filter(key=>flat(a[key])!==flat(b[key]));
  if(fields.length)delta.push({name,fields});
 }
 return delta;
}
export function decideVisualRender({previous,plan,action="",narration="",
 previousDisplay="layers",stageReady=true,style=""}={}){
 if(!plan)return {mode:"none",reason:"no_visual_plan",spriteNames:[],signature:""};
 const signature=visualSignature(plan,{style});
 const modified=changes(previous,plan);
 const characters=modified.filter(x=>x.fields.length);
 const propertyChanges=new Set(modified.flatMap(x=>x.fields));
 const physicalChanged=modified.some(x=>x.fields.includes("cast")||
  x.fields.includes("outfit")||x.fields.includes("equipment")||
  (x.fields.includes("pose")&&!smallPose.test(String((plan.characters||[])
   .find(c=>flat(c.name)===x.name)?.pose||""))));
 const cue=materialAction.test(String(narration||""));
 const physicalAction=modified.some(x=>x.fields.includes("action")&&
  materialAction.test(String((plan.characters||[]).find(c=>flat(c.name)===x.name)?.action||"")));
 const changedLocation=flat(previous?.location)!==flat(plan.location)||
  flat(previous?.environment)!==flat(plan.environment);
 const changedCamera=flat(previous?.camera)!==flat(plan.camera)&&cameraRequest.test(action);
 const reasons=[];
 if(changedLocation)reasons.push("location_or_environment_changed");
 if(physicalChanged)reasons.push("physical_state_changed");
 if(physicalAction||cue)reasons.push("physical_interaction");
 if(changedCamera)reasons.push("explicit_camera_change");
 if(reasons.length)
  return {mode:"cg",reason:reasons.join("+"),spriteNames:[],signature,changed:modified};
 // If the director wrote a different activity but no confirmed physical
 // action, do not treat mere prose as a reason to generate an image.
 const candidates=modified.filter(x=>x.fields.some(k=>
  k==="expression"||(k==="action"&&subtleAction.test(String((plan.characters||[])
   .find(c=>flat(c.name)===x.name)?.action||"")))));
 const spriteNames=candidates.map(x=>x.name);
 const layoutOnly=modified.length>0&&
   modified.every(x=>x.fields.every(key=>key==="pose"))&&
   modified.every(x=>smallPose.test(String((plan.characters||[])
    .find(c=>flat(c.name)===x.name)?.pose||"")));
 if(previousDisplay==="cg")
  return {mode:"none",reason:"reuse_existing_cg",spriteNames:[],signature,changed:modified};
 if(layoutOnly)
  return {mode:"none",reason:"sprite_layout_repositioned",
   spriteNames:[],signature,changed:modified};
 if(stageReady&&spriteNames.length)
  return {mode:"sprite",reason:"dialogue_expression_or_small_gesture",
   spriteNames,signature,changed:modified};
 return {mode:"none",reason:propertyChanges.size?
  "no_material_change_or_sprite_unavailable":"unchanged_visual_state",
  spriteNames:[],signature,changed:modified};
}
