import test from "node:test";
import assert from "node:assert/strict";
import {decideVisualRender,visualSignature,spriteSignature} from "../src/render-policy.mjs";

const a=(changes={})=>({name:"Mira",outfit:"green cloak",pose:"standing",
 expression:"neutral",equipment:"empty hands",action:"talking",...changes});
const scene=(changes={})=>({location:"Tirren market",environment:"stone square",
 camera:"two-shot",lighting:"daylight",activity:"a conversation",
 characters:[a()],...changes});
const choose=(prev,next,args={})=>decideVisualRender({
 previous:prev,plan:next,action:"What do you think?",
 narration:"She replies quietly.",style:"semireal",...args});

test("identical visual state reuses artwork even when the director asks to render",()=>{
 const v=scene();
 assert.equal(choose(v,{...v,render:true}).mode,"none");
 assert.equal(choose(v,{...v,render:true}).reason,"unchanged_visual_state");
});
test("emotion-only dialogue changes render only the affected sprite",()=>{
 const v=scene(),n=scene({characters:[a({expression:"smiling"})]});
 const d=choose(v,n);
 assert.equal(d.mode,"sprite");
 assert.deepEqual(d.spriteNames,["mira"]);
 assert.equal(choose(v,n,{previousDisplay:"cg"}).mode,"none",
   "A CG must stay visible rather than switching back to unrelated canonical sprites");
});
test("small positional blocking reuses existing sprite without GPU work",()=>{
 const prior=scene({characters:[a({pose:"standing at the left"})]});
 const next=scene({characters:[a({pose:"standing at the right"})]});
 const decision=choose(prior,next);
 assert.equal(decision.mode,"none");
 assert.equal(decision.reason,"sprite_layout_repositioned");
});
test("new physical contact or actual pose change produces a CG",()=>{
 const v=scene();
 for(const next of [
  scene({characters:[a({pose:"kneeling on the ground"})]}),
  scene({characters:[a({outfit:"green tunic"})]}),
  scene({location:"forest clearing"}),
  scene({characters:[a({action:"embracing another adult"})]})
 ]){
  assert.equal(choose(v,next).mode,"cg");
 }
 assert.equal(choose(v,scene(),{narration:"She embraces the traveler."}).mode,"cg");
});
test("director camera drift alone does not render; user-requested framing does",()=>{
 const prior=scene(),next=scene({camera:"cinematic close-up"});
 assert.equal(choose(prior,next).mode,"none");
 assert.equal(choose(prior,next,{action:"Change camera to a cinematic close-up"}).mode,"cg");
});
test("actor sprite cache separates emotion, clothing, location and style",()=>{
 const actor=a();
 const key=spriteSignature(actor,"market","semireal");
 assert.equal(key,spriteSignature({...actor},"market","semireal"));
 assert.notEqual(key,spriteSignature(a({expression:"smiling"}),"market","semireal"));
 assert.notEqual(key,spriteSignature(actor,"forest","semireal"));
 assert.notEqual(key,spriteSignature(actor,"market","anime"));
});
test("CG signature is stable on expressive changes but changes with pose",()=>{
 const prior=scene();
 const old=visualSignature(prior,{style:"realistic"});
 assert.equal(old,visualSignature(scene({characters:[a({expression:"smiling"})]}),
  {style:"realistic"}));
 assert.notEqual(old,visualSignature(scene({characters:[a({pose:"sitting"})]}),
  {style:"realistic"}));
});
