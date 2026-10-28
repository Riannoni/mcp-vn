import test from "node:test";
import assert from "node:assert/strict";
import {groundedLocalFrame} from "../src/local-visual-qa.mjs";

const visual={
 location:"Old market square",environment:"Medieval stone houses and shops",
 camera:"medium two-shot",activity:"A quiet conversation",characters:[
  {name:"Traveler",outfit:"blue mail armor",pose:"standing",equipment:"steel sword"},
  {name:"Guide",outfit:"green tunic",pose:"standing",equipment:"lantern"}
 ]
};
const base=()=>({
 id:"00000000-0000-4000-8000-000000000011",
 kind:"local_cg",status:"done",file:"accepted.png",
 asset_url:"https://example.org/assets/accepted.png",
 qa:{passed:true,semantic_status:"passed",
  metrics:{scene_count_verified:true,scene_location_verified:true,
   scene_action_contrast:0.71,scene_action_verified:false,
   checkpoint_name:"test_model.safetensors"}},
 spec:{preview_only:true,composition:"neural_story",
  local_session_id:"scene-1",local_visual_state:structuredClone(visual)}
});
const check=(j,plan=visual,opts={})=>groundedLocalFrame(j,{
 sessionId:"scene-1",visualState:plan,...opts
});
test("genuinely verified full-frame CG may seed an unchanged visual state",()=>{
 assert.deepEqual(check(base()),{ok:true,reason:"Verified scene, characters and location"});
});
test("a legacy job marked done without independent QA is NOT a valid next-frame seed",()=>{
 const j=base();delete j.qa.metrics.scene_count_verified;
 assert.equal(check(j).ok,false);
 j.qa.metrics.scene_count_verified=true;
 delete j.qa.metrics.scene_location_verified;
 assert.equal(check(j).ok,false);
});
test("a technically complete frame with only one principal or wrong location is rejected",()=>{
 const j=base();j.qa.metrics.scene_count_verified=false;
 assert.match(check(j).reason,/Principal characters/);
 j.qa.metrics.scene_count_verified=true;j.qa.metrics.scene_location_verified=false;
 assert.match(check(j).reason,/location/);
});
test("episode, character, wardrobe and scene changes disable old-image conditioning",()=>{
 const j=base();
 assert.equal(groundedLocalFrame(j,{sessionId:"other",visualState:visual}).ok,false);
 for(const patch of [
  {location:"Forest"},
  {environment:"Forest trees"},
  {camera:"wide overhead shot"},
  {activity:"They are walking instead of standing"},
  {characters:[{...visual.characters[0],action:"holds a lantern"},visual.characters[1]]},
  {characters:[{...visual.characters[0],outfit:"orange padded jacket"},visual.characters[1]]},
  {characters:[{...visual.characters[0],pose:"kneeling"},visual.characters[1]]},
  {characters:[{...visual.characters[0],equipment:"empty hands"},visual.characters[1]]},
  {characters:[visual.characters[0]]}
 ]){
  assert.equal(check(j,{...visual,...patch}).ok,false,
    "visual state change must invalidate old CG seed: "+JSON.stringify(patch).slice(0,70));
 }
});
test("optional video accepts only a verified frame matching the current cast and dress",()=>{
 const j=base();
 assert.equal(check(j,visual,{forVideo:true}).ok,true);
 assert.equal(check(j,{...visual,characters:[
  {...visual.characters[0],outfit:"black plate armor"},visual.characters[1]
 ]},{forVideo:true}).ok,false);
 assert.equal(check(j,{...visual,characters:[
  {...visual.characters[0],pose:"sitting"},visual.characters[1]
 ]},{forVideo:true}).ok,false);
});

test("compact job updates preserve independent scene QA evidence for the client",async()=>{
 const {compactJob}=await import("../src/game-delta.mjs");
 const update=compactJob(base());
 assert.equal(update.qa.metrics.scene_count_verified,true);
 assert.equal(update.qa.metrics.scene_location_verified,true);
 assert.equal(update.qa.metrics.scene_action_contrast,0.71);
 assert.equal(update.qa.metrics.scene_action_verified,false);
 assert.equal(update.qa.metrics.checkpoint_name,"test_model.safetensors");
});
