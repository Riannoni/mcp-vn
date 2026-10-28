import test from "node:test";
import assert from "node:assert/strict";
import {directorMessages,parseDirectorPlan,initialVisualState,
 normalizeVisualState,extractLocalVisual,visualContinuityIssues,DIRECTOR_SYSTEM} from "../src/local-director.mjs";

const game={
 hero:{name:"Макс Кроу",description:"Возраст: 34; dark hair and beard"},
 story:{summary:"Border city",characters:[{name:"Мира",age:26,description:"dark braided hair"}]},
 scene:{location:"Market square",time_of_day:"sunset",
  sprites:[
   {name:"Макс Кроу",outfit:"brown leather jacket",pose:"standing",emotion:"neutral"},
   {name:"Мира",outfit:"green traveling cloak",pose:"standing",emotion:"calm"}
  ]}
};
const initial=initialVisualState(game);
test("one visible character starts with single-person framing",()=>{
 const solo=initialVisualState({...game,scene:{...game.scene,
  sprites:game.scene.sprites.filter(s=>s.name==="Мира")}});
 assert.match(solo.camera,/single-character/u);
 assert.doesNotMatch(solo.camera,/two-shot/u);
});
const asReply=changes=>JSON.stringify({
 location:"Market square",environment:"Street among stalls",camera:"low diagonal side view",
 lighting:"warm evening sun",activity:"They walk along the stalls",
 characters:initial.characters.map(c=>({...c,...(changes[c.name]||{})})),
 render:true
});
test("director persists freeform armor, tools, items and arbitrary posture",()=>{
 const first=parseDirectorPlan(asReply({
  "Макс Кроу":{outfit:"blue chainmail over a red tunic",
    pose:"kneeling beside a fountain",equipment:"sheath holding an iron longsword",
    action:"examining a carved emblem",expression:"focused"},
  "Мира":{outfit:"black riding clothes with embroidered sleeves",
    pose:"lying on her side on a stone bench",equipment:"wooden bow on the ground",
    action:"reaching toward a dropped letter"}
 }),{previous:initial,game});
 assert.equal(first.warning,"");
 assert.equal(first.plan.render,true);
 assert.equal(first.plan.characters[0].outfit,"blue chainmail over a red tunic");
 assert.equal(first.plan.characters[0].equipment,"sheath holding an iron longsword");
 assert.equal(first.plan.characters[1].pose,"lying on her side on a stone bench");
 assert.equal(first.plan.characters[1].action,"reaching toward a dropped letter");
 assert.equal(first.plan.source,"ai_director");
});
test("hundreds of costume changes do not need a new enum or state schema",()=>{
 let previous=initial;
 for(let i=0;i<105;i++){
  const response=asReply({"Мира":{outfit:"travel outfit version "+i,
   pose:i%2?"sitting":"falling backward",
   equipment:"satchel contents "+i}});
  const next=parseDirectorPlan(response,{previous,game}).plan;
  assert.equal(next.render,true,"Change "+i+" must not be silently folded into a preset");
  previous={...next,last_queued:true};
 }
 assert.equal(previous.characters[1].outfit,"travel outfit version 104");
});
test("major wardrobe or equipment changes trigger artwork even if director mistakenly says no",()=>{
 const raw=JSON.stringify({
  characters:[{name:"Мира",outfit:"bronze plate armor",
    pose:"crouching beside an open chest",equipment:"crossbow with three bolts"}],
  render:false
 });
 const plan=parseDirectorPlan(raw,{previous:{...initial,last_queued:true},game}).plan;
 assert.equal(plan.render,true);
 assert.equal(plan.characters[1].outfit,"bronze plate armor");
 assert.equal(plan.characters[1].equipment,"crossbow with three bolts");
});
test("a repeated unchanged director beat is not rerendered for each sentence",()=>{
 const result=parseDirectorPlan(JSON.stringify({...initial,render:true}),{
  previous:{...initial,last_queued:true},game
 });
 assert.equal(result.plan.render,false);
});
test("characters and settings are persisted between turns even with partial field updates",()=>{
 const evolved=parseDirectorPlan(asReply({"Мира":{
  outfit:"white cloak",equipment:"short ceremonial sword",pose:"seated"}}),
 {previous:initial,game}).plan;
 const latest=parseDirectorPlan(JSON.stringify({
  camera:"full-height distant shot",characters:[{name:"Мира",expression:"curious"}],
  render:true
 }),{previous:{...evolved,last_queued:true},game}).plan;
 assert.equal(latest.characters[1].outfit,"white cloak");
 assert.equal(latest.characters[1].equipment,"short ceremonial sword");
 assert.equal(latest.characters[1].pose,"seated");
 assert.equal(latest.characters[1].expression,"curious");
});
test("malformed model output leaves existing scene unchanged, rather than guessing a pose",()=>{
 const broken=parseDirectorPlan("This is not JSON",{
  previous:{...initial,last_queued:true},game
 });
 assert.equal(broken.plan.render,false);
 assert.match(broken.warning,/структурированный/u);
 assert.equal(broken.plan.characters[1].outfit,"green traveling cloak");
});
test("old saves can be upgraded to a scene state while keeping canonical wardrobe",()=>{
 const result=normalizeVisualState({shot:"embrace",wardrobe:"canonical",mood:"warm",
  last_queued:true},game);
 assert.equal(result.schema,2);
 assert.equal(result.characters[1].outfit,"green traveling cloak");
 assert.equal(result.camera,"embrace");
 assert.equal(result.last_queued,true);
});
test("director is role-separated and retains actionable character details",()=>{
 const messages=directorMessages({game,previous:initial,
  participants:[{name:"Макс Кроу",age:34},{name:"Мира",age:26}],
  location:"Market square",action:"Let's move",
  narration:"Mira slowly sits down",
  recent_dialogue:[{role:"player",text:"Do you want to sit?"}]
 });
 assert.deepEqual(messages.map(x=>x.role),["system","user"]);
 assert.ok(DIRECTOR_SYSTEM.includes("never select from preset"));
 const payload=JSON.parse(messages[1].content);
 assert.equal(payload.previous_visual.characters[1].outfit,"green traveling cloak");
 assert.equal(payload.adult_cast[1].age,26);
});
test("incompatible clothing is flagged for reconciliation without selecting garments",()=>{
 const unchanged={characters:[{name:"Мира",outfit:"fully dressed green cloak",pose:"standing"}]};
 const mismatches=visualContinuityIssues({plan:unchanged,
  action:"Мира стоит передо мной с обнажённым телом.",
  narration:"Мира медленно подошла к стене."});
 assert.equal(mismatches.length,1);
 const reconciled=visualContinuityIssues({plan:{characters:[
  {name:"Мира",outfit:"a cloak set aside nearby",pose:"sitting"}
 ]},action:"Мира стоит передо мной с обнажённым телом.",
  narration:"Мира медленно подошла к стене."});
 assert.deepEqual(reconciled,[]);
 const refused=visualContinuityIssues({plan:unchanged,
  action:"Мира стоит передо мной с обнажённым телом.",
  narration:"Мира отказалась раздеваться и сохранила плащ."});
 assert.deepEqual(refused,[]);
});
test("internal v5.9 visual control tag is removed from user narration",()=>{
 const x=extractLocalVisual("Mira nods. \n[[VN_VISUAL shot=embrace wardrobe=canonical mood=smile render=yes]]");
 assert.equal(x.narration,"Mira nods.");
});
